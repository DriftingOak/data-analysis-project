#!/usr/bin/env python3
"""
POLYMARKET BOT - Main Entry Point (Optimized)
==============================================
Paper trading with 24 strategies. Markets are evaluated ONCE,
then each strategy filters from the pre-computed candidate pool.

Usage:
    python bot.py --paper              # Standard strategies (base group)
    python bot.py --paper all          # ALL 24 strategies
    python bot.py --paper tier1        # Tier 1 controls only
    python bot.py --paper balanced     # Single strategy
    python bot.py --sell "iran"        # Manually sell matching positions
    python bot.py --strategies         # Show available strategies
"""

import sys
import json
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict

import config
import api

# Import geopolitical filters
try:
    from trade_filter import is_geopolitical, get_cluster, classify
except ImportError:
    try:
        from filters import is_geopolitical, get_cluster
    except ImportError:
        # Minimal fallback
        def is_geopolitical(q):
            kw = ["strike", "attack", "war", "invasion", "bomb", "missile",
                   "ceasefire", "sanctions", "troops", "nuclear", "military"]
            q_l = q.lower()
            return any(k in q_l for k in kw)
        def get_cluster(q):
            q_l = q.lower()
            if any(k in q_l for k in ["ukraine", "russia", "kyiv", "crimea", "kursk"]):
                return "ukraine"
            if any(k in q_l for k in ["israel", "gaza", "iran", "hamas", "hezbollah", "yemen", "houthi"]):
                return "mideast"
            if any(k in q_l for k in ["china", "taiwan", "beijing"]):
                return "china"
            return "other"


# =============================================================================
# LOGGING
# =============================================================================

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def send_telegram(message: str):
    """Send Telegram notification (best-effort)."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


# =============================================================================
# ENRICHED CANDIDATE (pre-computed once, shared across strategies)
# =============================================================================

@dataclass
class EnrichedMarket:
    """All data needed to decide on a market, computed once."""
    market_id: str
    question: str
    price_yes: float
    volume: float
    cluster: str
    days_to_close: float
    end_ts: float
    start_ts: float
    token_id_yes: str
    token_id_no: str
    event_id: str          # For event_cap
    structure: str         # "series" or "" — for exclude_series filter
    raw: dict              # Original market data (for resolution checking)


def precompute_candidates(markets: list, current_ts: float) -> List[EnrichedMarket]:
    """Evaluate ALL markets once → list of geopolitical candidates.
    
    This is the expensive step (keyword matching, parsing, validation).
    Done ONCE, then each strategy just filters numerically.
    """
    candidates = []
    
    for market in markets:
        question = market.get("question", "")
        
        # 1) Geopolitical filter (the expensive check)
        if not is_geopolitical(question):
            continue
        
        # 2) Parse timestamps
        timestamps = api.parse_market_timestamps(market)
        start_ts = timestamps.get("start_ts")
        end_ts = timestamps.get("end_ts")
        
        if not start_ts or not end_ts:
            continue
        
        # 3) Basic time validity
        hours_since_open = (current_ts - start_ts) / 3600
        hours_until_end = (end_ts - current_ts) / 3600
        
        # Skip if too new or about to close
        buffer_hours = getattr(config, "BUFFER_HOURS", 48)
        if hours_since_open < buffer_hours or hours_until_end < buffer_hours:
            continue
        
        # 4) Parse price
        try:
            prices_raw = market.get("outcomePrices", "")
            if isinstance(prices_raw, str) and prices_raw:
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw or []
            price_yes = float(prices[0]) if prices else None
        except (json.JSONDecodeError, IndexError, ValueError):
            continue
        
        if price_yes is None or price_yes <= 0 or price_yes >= 1:
            continue
        
        # 5) Volume
        volume = float(market.get("volume", 0) or 0)
        
        # 6) Token IDs
        tokens = api.get_token_ids(market)
        token_yes = tokens.get("YES", "")
        token_no = tokens.get("NO", "")
        
        # 7) Metadata
        days_to_close = hours_until_end / 24
        event_id = market.get("groupItemTitle", "") or market.get("slug", "")
        
        # Detect series structure (for exclude_series filter)
        # Series markets typically share an event/group
        structure = ""
        if market.get("groupItemTitle"):
            structure = "series"
        
        candidates.append(EnrichedMarket(
            market_id=market.get("id", market.get("conditionId", "")),
            question=question[:120],
            price_yes=price_yes,
            volume=volume,
            cluster=get_cluster(question),
            days_to_close=days_to_close,
            end_ts=end_ts,
            start_ts=start_ts,
            token_id_yes=token_yes,
            token_id_no=token_no,
            event_id=event_id,
            structure=structure,
            raw=market,
        ))
    
    return candidates


# =============================================================================
# STRATEGY FILTERING (fast — just numeric comparisons)
# =============================================================================

def filter_for_strategy(
    candidates: List[EnrichedMarket],
    strat: dict,
) -> List[EnrichedMarket]:
    """Filter pre-computed candidates for a specific strategy.
    
    This is FAST — no keyword matching, no API calls, just comparisons.
    """
    from strategies import get_zone_for_volume
    
    filtered = []
    
    # Strategy params
    min_vol = strat.get("min_volume", 0)
    max_vol = strat.get("max_volume", float("inf"))
    deadline_min = strat.get("deadline_min", 3)
    deadline_max = strat.get("deadline_max", None)
    exclude_series = strat.get("exclude_series", False)
    
    for c in candidates:
        # Volume filter
        if c.volume < min_vol or c.volume > max_vol:
            continue
        
        # Deadline filter
        if c.days_to_close < deadline_min:
            continue
        if deadline_max is not None and c.days_to_close > deadline_max:
            continue
        
        # Exclude series
        if exclude_series and c.structure == "series":
            continue
        
        # Price zone (simple or multi-bucket)
        zone = get_zone_for_volume(strat, c.volume)
        if zone is None:
            # Dead zone — skip
            continue
        
        price_min, price_max = zone
        if not (price_min <= c.price_yes <= price_max):
            continue
        
        filtered.append(c)
    
    return filtered


def sort_candidates(candidates: List[EnrichedMarket], priority: str) -> List[EnrichedMarket]:
    """Sort candidates by strategy priority."""
    if priority == "price_high":
        # Higher YES price first (more edge for NO bets)
        return sorted(candidates, key=lambda c: c.price_yes, reverse=True)
    
    elif priority == "volume_low":
        # Lower volume first (more inefficient markets)
        return sorted(candidates, key=lambda c: c.volume)
    
    elif priority == "rotation":
        # Composite: rank by volume_low + deadline_short + price_high
        # Lower score = better
        def rotation_score(c):
            # Normalize each dimension to ~0-100 range
            vol_score = min(c.volume / 5000, 100)    # Lower volume = lower score = better
            dl_score = min(c.days_to_close, 100)      # Shorter deadline = lower score = better
            price_score = (1 - c.price_yes) * 100     # Higher YES = lower (1-p) = better
            return vol_score + dl_score + price_score
        return sorted(candidates, key=rotation_score)
    
    else:
        return candidates


# =============================================================================
# TRADE SELECTION (with new features: event_cap, adaptive sizing)
# =============================================================================

def select_trades(
    candidates: List[EnrichedMarket],
    strat: dict,
    cash_available: float,
    current_exposure: float,
    exposure_by_cluster: Dict[str, float],
    existing_market_ids: Set[str],
    existing_event_counts: Dict[str, int],
    bankroll: float,
) -> List[Tuple[EnrichedMarket, float]]:
    """Select trades with new features. Returns list of (candidate, bet_size)."""
    from strategies import get_bet_size
    
    max_total = bankroll * strat.get("max_total_exposure_pct", 0.90)
    max_cluster = bankroll * strat.get("max_cluster_exposure_pct", 0.30)
    event_cap = strat.get("event_cap", 3)
    
    # Sort by priority
    sorted_cands = sort_candidates(candidates, strat.get("priority", "price_high"))
    
    selected = []
    sim_exposure = current_exposure
    sim_cluster = dict(exposure_by_cluster)
    sim_cash = cash_available
    sim_event_counts = dict(existing_event_counts)
    
    for c in sorted_cands:
        # Skip if already in this market
        if c.market_id in existing_market_ids:
            continue
        
        # Event cap
        event_count = sim_event_counts.get(c.event_id, 0)
        if event_count >= event_cap:
            continue
        
        # Get bet size (adaptive or fixed)
        bet_size = get_bet_size(strat, c.volume)
        
        # Cash check
        if sim_cash < bet_size:
            break
        
        # Total exposure check
        if sim_exposure + bet_size > max_total:
            continue
        
        # Cluster exposure check
        cluster_exp = sim_cluster.get(c.cluster, 0)
        if cluster_exp + bet_size > max_cluster:
            continue
        
        # Accept
        selected.append((c, bet_size))
        sim_cash -= bet_size
        sim_exposure += bet_size
        sim_cluster[c.cluster] = cluster_exp + bet_size
        sim_event_counts[c.event_id] = event_count + 1
        existing_market_ids.add(c.market_id)
    
    return selected


# =============================================================================
# RESOLUTION CHECKING (batch, shared across strategies)
# =============================================================================

def batch_fetch_closed_markets(
    missing_ids: Set[str], market_lookup: Dict[str, dict]
) -> Dict[str, dict]:
    """Fetch closed markets that are no longer in the open markets feed.
    
    Returns dict of market_id -> market_data for resolved markets.
    """
    resolved = {}
    for mid in missing_ids:
        if mid in market_lookup:
            continue  # Already have it
        try:
            data = api.fetch_market_by_id(mid)
            if data:
                resolved[mid] = data
        except Exception:
            pass
    return resolved


# =============================================================================
# PAPER TRADING MAIN LOOP
# =============================================================================

def run_paper_trading(strategy_name: str = None):
    """Run paper trading — optimized for many strategies."""
    import paper_trading as pt
    import strategies as strat_config
    
    run_start = datetime.now()
    log("=" * 60)
    log("POLYMARKET BOT — PAPER TRADING")
    log("=" * 60)
    
    # ── Determine strategies to run ──────────────────────────────────────
    if strategy_name is None:
        strategy_name = "standard"
    
    if strategy_name in strat_config.STRATEGY_GROUPS:
        group_names = strat_config.STRATEGY_GROUPS[strategy_name]
        strategies = {k: strat_config.STRATEGIES[k] for k in group_names}
        log(f"Group '{strategy_name}': {len(strategies)} strategies")
    elif strategy_name in strat_config.STRATEGIES:
        strategies = {strategy_name: strat_config.STRATEGIES[strategy_name]}
    else:
        log(f"Unknown strategy/group: '{strategy_name}'", "ERROR")
        log(f"Groups: {list(strat_config.STRATEGY_GROUPS.keys())}")
        return
    
    log(f"Strategies: {', '.join(strategies.keys())}")
    
    # ── Step 1: Fetch markets ONCE ───────────────────────────────────────
    log("\nFetching markets...")
    t0 = datetime.now()
    markets = api.fetch_open_markets(limit=5000)
    log(f"Fetched {len(markets)} markets in {(datetime.now()-t0).total_seconds():.1f}s")
    
    market_lookup = {}
    for m in markets:
        mid = m.get("id") or m.get("conditionId")
        if mid:
            market_lookup[mid] = m
    
    # ── Step 2: Pre-compute geopolitical candidates ONCE ─────────────────
    current_ts = datetime.now().timestamp()
    t0 = datetime.now()
    all_candidates = precompute_candidates(markets, current_ts)
    log(f"Pre-computed {len(all_candidates)} geopolitical candidates in {(datetime.now()-t0).total_seconds():.1f}s")
    
    # ── Step 3: Collect ALL open position market IDs (for batch resolution) ──
    all_open_mids: Set[str] = set()
    portfolios = {}
    
    for strat_name, strat_params in strategies.items():
        portfolio_file = strat_params.get("portfolio_file", f"portfolio_{strat_name}.json")
        # Portfolio files live at repo root (git add portfolio_*.json)
        
        portfolio = pt.load_portfolio(
            portfolio_file=portfolio_file,
            initial_bankroll=strat_params.get("bankroll", getattr(config, "BANKROLL", 1000)),
            entry_cost_rate=strat_params.get("entry_cost_rate", getattr(config, "ENTRY_COST_RATE", 0.03)),
        )
        portfolios[strat_name] = (portfolio, portfolio_file)
        
        for pos in portfolio.positions:
            if pos.status == "open":
                all_open_mids.add(pos.market_id)
    
    # ── Step 4: Batch-fetch closed markets ───────────────────────────────
    missing_mids = all_open_mids - set(market_lookup.keys())
    if missing_mids:
        log(f"Fetching {len(missing_mids)} closed markets for resolution...")
        t0 = datetime.now()
        closed_data = batch_fetch_closed_markets(missing_mids, market_lookup)
        market_lookup.update(closed_data)
        log(f"Fetched {len(closed_data)} closed markets in {(datetime.now()-t0).total_seconds():.1f}s")
    
    # ── Step 5: Process each strategy ────────────────────────────────────
    summary_lines = [
        f"📊 <b>Paper Trading</b> ({len(strategies)} strategies)",
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    
    for strat_name, strat_params in strategies.items():
        portfolio, portfolio_file = portfolios[strat_name]
        
        # ── 5a. Update prices for open positions ─────────────────────────
        for pos in portfolio.positions:
            if pos.status != "open":
                continue
            mdata = market_lookup.get(pos.market_id)
            if mdata:
                try:
                    prices_raw = mdata.get("outcomePrices", "")
                    if isinstance(prices_raw, str) and prices_raw:
                        prices = json.loads(prices_raw)
                    else:
                        prices = prices_raw or []
                    if prices:
                        price_yes = float(prices[0])
                        pos.price_yes_current = price_yes
                        pos.current_price = 1 - price_yes if pos.bet_side == "NO" else price_yes
                except Exception:
                    pass
        
        # ── 5b. Check resolutions ───────────────────────────────────────
        resolved_count = 0
        for pos in list(portfolio.positions):
            if pos.status != "open":
                continue
            mdata = market_lookup.get(pos.market_id)
            if mdata:
                outcome = pt.check_resolution(mdata)
                if outcome:
                    pnl = pt.settle_position(pos, outcome)
                    portfolio.closed_trades.append(pos)
                    resolved_count += 1
                    emoji = "✅" if pos.resolution == "win" else "❌"
                    log(f"  {emoji} {pos.bet_side} resolved: {outcome.upper()} | P&L: ${pnl:+.2f}")
        
        if resolved_count > 0:
            pt.update_portfolio_stats(portfolio)
        
        # ── 5c. Filter candidates for this strategy ──────────────────────
        strat_candidates = filter_for_strategy(all_candidates, strat_params)
        
        # ── 5d. Calculate exposure ───────────────────────────────────────
        exposure_total, exposure_by_cluster = pt.get_open_exposure(portfolio)
        existing_ids = {p.market_id for p in portfolio.positions if p.status == "open"}
        cash_available = portfolio.bankroll_current - exposure_total
        
        # Count positions per event_id
        event_counts: Dict[str, int] = {}
        for pos in portfolio.positions:
            if pos.status == "open":
                eid = getattr(pos, "event_id", "") or ""
                event_counts[eid] = event_counts.get(eid, 0) + 1
        
        # ── 5e. Select trades ────────────────────────────────────────────
        selected = select_trades(
            candidates=strat_candidates,
            strat=strat_params,
            cash_available=cash_available,
            current_exposure=exposure_total,
            exposure_by_cluster=exposure_by_cluster,
            existing_market_ids=set(existing_ids),  # copy
            existing_event_counts=event_counts,
            bankroll=portfolio.bankroll_current,
        )
        
        # ── 5f. Execute paper trades ─────────────────────────────────────
        for candidate, bet_size in selected:
            bet_side = strat_params.get("bet_side", "NO")
            if bet_side == "NO":
                token_id = candidate.token_id_no
                entry_price = 1 - candidate.price_yes
            else:
                token_id = candidate.token_id_yes
                entry_price = candidate.price_yes
            
            expected_close = datetime.fromtimestamp(candidate.end_ts).strftime("%Y-%m-%d")
            
            pt.paper_buy(
                portfolio=portfolio,
                market_id=candidate.market_id,
                question=candidate.question,
                token_id=token_id,
                bet_side=bet_side,
                entry_price=entry_price,
                size_usd=bet_size,
                cluster=candidate.cluster,
                expected_close=expected_close,
            )
        
        # ── 5g. Save portfolio ───────────────────────────────────────────
        pt.save_portfolio(portfolio, portfolio_file)
        
        # ── 5h. Summary line ─────────────────────────────────────────────
        open_count = len([p for p in portfolio.positions if p.status == "open"])
        summary_lines.append(
            f"<b>{strat_name}</b>: ${portfolio.total_pnl:+.2f} "
            f"({portfolio.wins}W/{portfolio.losses}L) | "
            f"{open_count} open | +{len(selected)} new | {resolved_count} resolved"
        )
    
    # ── Step 6: Notifications ────────────────────────────────────────────
    duration = (datetime.now() - run_start).total_seconds()
    summary_lines.append(f"\n⏱ {duration:.0f}s | {len(all_candidates)} geo candidates")
    
    # Only send full summary if ≤ 8 strategies, otherwise compact
    if len(strategies) <= 8:
        send_telegram("\n".join(summary_lines))
    else:
        # Compact: just totals
        total_new = sum(1 for s in strategies for _ in [])  # placeholder
        send_telegram(
            f"📊 Paper trading: {len(strategies)} strategies updated in {duration:.0f}s\n"
            f"Candidates pool: {len(all_candidates)} geo markets"
        )
    
    log(f"\n{'='*60}")
    log(f"COMPLETE in {duration:.1f}s ({len(strategies)} strategies, {len(all_candidates)} candidates)")
    log(f"{'='*60}")


# =============================================================================
# MANUAL SELL
# =============================================================================

def manual_sell(search_term: str):
    """Manually sell positions matching a search term across all strategies."""
    import paper_trading as pt
    import strategies as strat_config
    
    count = 0
    for strat_name, strat_params in strat_config.STRATEGIES.items():
        portfolio_file = strat_params.get("portfolio_file", f"portfolio_{strat_name}.json")
        
        if not Path(portfolio_file).exists():
            continue
        
        portfolio = pt.load_portfolio(
            portfolio_file=portfolio_file,
            initial_bankroll=strat_params.get("bankroll", 1000),
            entry_cost_rate=strat_params.get("entry_cost_rate", 0.03),
        )
        
        sold = False
        for pos in portfolio.positions:
            if pos.status == "open" and search_term.lower() in pos.question.lower():
                pos.status = "sold"
                pos.pnl = 0  # Manual sell at current price (simplified)
                sold = True
                count += 1
                log(f"Sold [{strat_name}]: {pos.question[:60]}")
        
        if sold:
            pt.save_portfolio(portfolio, portfolio_file)
    
    log(f"Sold {count} position(s) matching '{search_term}'")


# =============================================================================
# CLI
# =============================================================================

def main():
    args = sys.argv[1:]
    
    if not args or "--help" in args:
        print(__doc__)
        return
    
    if "--strategies" in args:
        import strategies as strat_config
        strat_config.print_strategies()
        return
    
    if "--sell" in args:
        idx = args.index("--sell")
        if idx + 1 < len(args):
            manual_sell(args[idx + 1])
        else:
            print("Usage: python bot.py --sell <search_term>")
        return
    
    if "--paper" in args:
        idx = args.index("--paper")
        strategy_name = args[idx + 1] if idx + 1 < len(args) else None
        run_paper_trading(strategy_name)
        return
    
    print("Unknown command. Use --help for usage.")


if __name__ == "__main__":
    main()
