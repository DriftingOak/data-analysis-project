#!/usr/bin/env python3
"""
POLYMARKET BOT - Main Entry Point
==================================
Runs the trading strategy and places orders.

Usage:
    python bot.py                        # Dry run (default)
    python bot.py --live                 # Live trading (real orders)
    python bot.py --scan-only            # Just scan markets, no orders
    python bot.py --paper                # Paper trading - standard strategies
    python bot.py --paper balanced       # Paper trading - single strategy
    python bot.py --paper unlimited      # Paper trading - unlimited group
    python bot.py --paper all            # Paper trading - ALL strategies
    python bot.py --paper --strategy balanced  # Paper trading - single strategy
    python bot.py --sell "iran"          # Manually sell position(s) matching "iran"
    python bot.py --strategies           # Show available strategies
    python bot.py --help                 # Show this help

Strategy Groups:
    standard    - conservative, balanced, aggressive, volume_sweet
    unlimited   - unlimited_* strategies (no exposure limits)
    experimental- new strategies to test
    all         - everything
"""

import sys
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

import config
import api
import strategy

# =============================================================================
# LOGGING
# =============================================================================

def log(msg: str, level: str = "INFO"):
    """Simple logging with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def save_run_history(run_data: Dict[str, Any]):
    """Append run to history file."""
    try:
        try:
            with open(config.LOG_FILE, "r") as f:
                history = json.load(f)
        except FileNotFoundError:
            history = []
        
        history.append(run_data)
        history = history[-100:]  # Keep last 100
        
        with open(config.LOG_FILE, "w") as f:
            json.dump(history, f, indent=2)
            
    except Exception as e:
        log(f"Failed to save history: {e}", "WARN")


# =============================================================================
# NOTIFICATIONS
# =============================================================================

def send_telegram(message: str):
    """Send notification via Telegram."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        log(f"Telegram notification failed: {e}", "WARN")


# =============================================================================
# SNAPSHOT INTEGRATION
# =============================================================================

def collect_all_eligible_markets(markets: List[Dict], current_ts: float) -> List:
    """Collect ALL geopolitical markets for snapshot (regardless of strategy params).
    
    This captures the full universe of eligible markets at this point in time,
    allowing replay with any strategy parameters later.
    """
    from snapshot import create_market_snapshot, MarketSnapshot
    
    eligible = []
    
    for market in markets:
        question = market.get("question", "")
        
        # Only filter: must be geopolitical and not excluded
        if not strategy.is_geopolitical(question):
            continue
        
        # Get timestamps
        timestamps = api.parse_market_timestamps(market)
        tokens = api.get_token_ids(market)
        
        # Basic time validation (must have valid timestamps)
        start_ts = timestamps.get("start_ts")
        end_ts = timestamps.get("end_ts")
        if not start_ts or not end_ts:
            continue
        
        # Must not be closed yet
        if end_ts < current_ts:
            continue
        
        # Get cluster
        cluster = strategy.get_cluster(question)
        
        # Create snapshot
        snap = create_market_snapshot(market, timestamps, tokens, current_ts, cluster)
        eligible.append(snap)
    
    return eligible


def save_run_snapshot(markets: List[Dict], current_ts: float, total_scanned: int) -> Optional[str]:
    """Save a snapshot of all eligible markets."""
    try:
        from snapshot import save_snapshot
        
        eligible = collect_all_eligible_markets(markets, current_ts)
        
        if eligible:
            filepath = save_snapshot(
                markets=eligible,
                total_scanned=total_scanned,
                note=f"Bot run at {datetime.now().isoformat()}"
            )
            return filepath
        else:
            log("No eligible markets to snapshot", "WARN")
            return None
            
    except ImportError:
        log("Snapshot module not available", "WARN")
        return None
    except Exception as e:
        log(f"Failed to save snapshot: {e}", "ERROR")
        return None


# =============================================================================
# PAPER TRADING MODE
# =============================================================================

def run_paper_trading(strategy_name: str = None):
    """Run paper trading mode.
    
    Args:
        strategy_name: Name of strategy, group name, or None to run standard group
    """
    import paper_trading as pt
    import strategies as strat_config
    
    run_start = datetime.now()
    log("=" * 60)
    log("POLYMARKET BOT - PAPER TRADING MODE")
    log("=" * 60)
    
    # Determine which strategies to run
    if strategy_name is None:
        # Default: standard group
        strategies_to_run = {k: strat_config.STRATEGIES[k] 
                           for k in strat_config.STRATEGY_GROUPS["standard"]}
        log("Running STANDARD strategies (use --paper all for everything)")
    elif strategy_name in strat_config.STRATEGY_GROUPS:
        # It's a group name
        group_strats = strat_config.STRATEGY_GROUPS[strategy_name]
        strategies_to_run = {k: strat_config.STRATEGIES[k] for k in group_strats}
        log(f"Running {strategy_name.upper()} group ({len(strategies_to_run)} strategies)")
    elif strategy_name in strat_config.STRATEGIES:
        # Single strategy
        strategies_to_run = {strategy_name: strat_config.STRATEGIES[strategy_name]}
    else:
        log(f"ERROR: Unknown strategy or group '{strategy_name}'", "ERROR")
        log(f"Strategies: {list(strat_config.STRATEGIES.keys())}")
        log(f"Groups: {list(strat_config.STRATEGY_GROUPS.keys())}")
        return
    
    log(f"Strategies: {list(strategies_to_run.keys())}")
    
    # Fetch all markets once (shared across strategies)
    log("\nFetching markets...")
    markets = api.fetch_open_markets(limit=5000)
    log(f"Found {len(markets)} markets")
    
    # Build market lookup
    market_lookup = {m.get("id") or m.get("conditionId"): m for m in markets}
    current_ts = datetime.now().timestamp()
    
    # === SAVE SNAPSHOT ===
    log("\n--- SAVING SNAPSHOT ---")
    snapshot_path = save_run_snapshot(markets, current_ts, len(markets))
    if snapshot_path:
        log(f"Snapshot saved: {snapshot_path}")
    
    # Prepare summary for Telegram
    summary_lines = [
        f"📊 <b>Paper Trading Update</b>",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ""
    ]
    
    # Run each strategy
    for strat_name, strat_params in strategies_to_run.items():
        log("\n" + "=" * 60)
        display_name = strat_params.get("name", strat_name)
        log(f"STRATEGY: {display_name}")
        log("=" * 60)
        
        portfolio_file = strat_params.get("portfolio_file", f"portfolio_{strat_name}.json")
        initial_bankroll = strat_params.get("bankroll", 5000.0)
        
        # Load portfolio for this strategy
        portfolio = pt.load_portfolio(
            portfolio_file=portfolio_file,
            initial_bankroll=initial_bankroll,
            entry_cost_rate=strat_params.get("entry_cost_rate", getattr(config, "ENTRY_COST_RATE", getattr(config, "PAPER_ENTRY_COST_RATE", 0.03))),
        )
        
        # 1) Check resolutions of open positions
        log("Checking open positions for resolutions...")
        open_positions = [p for p in portfolio.positions if p.status == "open"]
        newly_closed = 0
        
        for pos in open_positions:
            market_data = market_lookup.get(pos.market_id)
            
            # If market not in open markets, it might be closed - fetch it directly
            if not market_data:
                market_data = api.fetch_market_by_id(pos.market_id)
            
            if market_data:
                outcome = pt.check_resolution(market_data)
                if outcome:
                    pnl = pt.settle_position(pos, outcome)
                    portfolio.closed_trades.append(pos)
                    newly_closed += 1
                    emoji = "✅" if pos.resolution == "win" else "❌"
                    log(f"  {emoji} {pos.bet_side} resolved: {outcome.upper()} | P&L: ${pnl:+.2f}")
        
        if newly_closed > 0:
            pt.update_portfolio_stats(portfolio)
            log(f"{newly_closed} positions resolved")
        
        # 2) Evaluate new candidates with this strategy's params
        log("Evaluating markets for new positions...")
        candidates = []
        
        # Check for cluster filter
        cluster_filter = strat_params.get("cluster_filter")
        
        for market in markets:
            timestamps = api.parse_market_timestamps(market)
            tokens = api.get_token_ids(market)
            
            candidate = strategy.evaluate_market(
                market, timestamps, tokens, current_ts,
                strategy_params=strat_params,
            )
            
            if candidate:
                # Apply cluster filter if specified
                if cluster_filter and candidate.cluster not in cluster_filter:
                    continue
                candidates.append(candidate)
        
        log(f"Found {len(candidates)} qualifying candidates")
        
        # 3) Select and execute paper trades
        exposure_total, exposure_by_cluster = pt.get_open_exposure(portfolio)
        existing_ids = pt.get_open_market_ids(portfolio)
        available_cash = portfolio.bankroll_current - exposure_total
        
        # Use strategy-specific exposure limits
        max_total_exp = strat_params.get("max_total_exposure_pct", 0.60)
        max_cluster_exp = strat_params.get("max_cluster_exposure_pct", 0.20)
        bet_size = strat_params.get("bet_size", config.BET_SIZE)
        
        selected = strategy.select_trades(
            candidates=candidates,
            cash_available=available_cash,
            current_exposure=exposure_total,
            exposure_by_cluster=exposure_by_cluster,
            bankroll=portfolio.bankroll_current,
            existing_market_ids=existing_ids,
            max_exposure_pct=max_total_exp,
            max_cluster_pct=max_cluster_exp,
            bet_size=bet_size,
        )
        
        log(f"Selected {len(selected)} new trades")
        
        # Execute paper trades
        for trade in selected:
            expected_close = datetime.fromtimestamp(trade.end_ts).strftime("%Y-%m-%d")
            
            pt.paper_buy(
                portfolio=portfolio,
                market_id=trade.market_id,
                question=trade.question,
                token_id=trade.token_id,
                bet_side=trade.bet_side,
                entry_price=trade.price_entry,
                size_usd=bet_size,
                cluster=trade.cluster,
                expected_close=expected_close,
            )
            
            log(f"  📝 {trade.bet_side} @ {trade.price_entry:.1%} | [{trade.cluster}] {trade.question[:40]}...")
        
        # 4) Update current prices for open positions
        log("Updating current prices...")
        for pos in portfolio.positions:
            if pos.status != "open":
                continue
            
            market_data = market_lookup.get(pos.market_id)
            if market_data:
                try:
                    prices_raw = market_data.get("outcomePrices", "")
                    if isinstance(prices_raw, str) and prices_raw:
                        prices = json.loads(prices_raw)
                    else:
                        prices = prices_raw or []
                    
                    if prices:
                        price_yes = float(prices[0])
                        pos.price_yes_current = price_yes
                        pos.current_price = 1 - price_yes if pos.bet_side == "NO" else price_yes
                except:
                    pass
        
        # 5) Save portfolio
        pt.save_portfolio(portfolio, portfolio_file)
        
        # 6) Summary for this strategy
        pt.print_portfolio_summary(portfolio, display_name)
        
        # Add to Telegram summary
        open_count = len([p for p in portfolio.positions if p.status == "open"])
        summary_lines.append(
            f"<b>{display_name}</b>: ${portfolio.total_pnl:+.2f} "
            f"({portfolio.wins}W/{portfolio.losses}L) | {open_count} open"
        )
    
    # Send consolidated Telegram notification
    if len(strategies_to_run) <= 6:  # Don't spam if running many strategies
        send_telegram("\n".join(summary_lines))
    else:
        send_telegram(f"📊 Paper trading complete: {len(strategies_to_run)} strategies updated")
    
    log("\n" + "=" * 60)
    log("PAPER TRADING COMPLETE")
    log("=" * 60)


# =============================================================================
# MANUAL SELL
# =============================================================================

def manual_sell(search_term: str):
    """Manually sell positions matching a search term."""
    import strategies as strat_config
    import paper_trading as pt
    
    search_term = search_term.lower()
    log(f"Searching for positions matching: '{search_term}'")
    
    matches = []
    
    for strat_name, strat_params in strat_config.STRATEGIES.items():
        portfolio_file = strat_params.get("portfolio_file", f"portfolio_{strat_name}.json")
        
        try:
            portfolio = pt.load_portfolio(portfolio_file)
        except:
            continue
        
        for pos in portfolio.positions:
            if pos.status != "open":
                continue
            
            if search_term in pos.question.lower() or search_term in pos.market_id:
                matches.append({
                    "strategy": strat_name,
                    "portfolio": portfolio,
                    "portfolio_file": portfolio_file,
                    "position": pos,
                })
    
    if not matches:
        log(f"No open positions found matching '{search_term}'")
        return
    
    log(f"Found {len(matches)} matching position(s):")
    for i, m in enumerate(matches, 1):
        pos = m["position"]
        log(f"  {i}. [{m['strategy']}] {pos.bet_side} @ {pos.entry_price:.1%} | {pos.question[:50]}...")
    
    # Ask for confirmation
    print("\nEnter number to sell (0 to cancel): ", end="")
    try:
        choice = input().strip()
        choice_num = int(choice)
        
        if choice_num == 0:
            log("Cancelled")
            return
        
        if choice_num < 1 or choice_num > len(matches):
            log("Invalid choice", "ERROR")
            return
        
        selected = matches[choice_num - 1]
    except (ValueError, KeyboardInterrupt):
        log("Cancelled")
        return
    
    pos = selected["position"]
    portfolio = selected["portfolio"]
    portfolio_file = selected["portfolio_file"]
    
    # Fetch current price
    log(f"Fetching current price for {pos.market_id}...")
    try:
        url = f"https://gamma-api.polymarket.com/markets/{pos.market_id}"
        resp = requests.get(url, timeout=10)
        market = resp.json()
        
        prices_raw = market.get("outcomePrices", "")
        if isinstance(prices_raw, str) and prices_raw:
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw or []
        
        current_yes = float(prices[0]) if prices else None
    except Exception as e:
        log(f"Failed to fetch price: {e}", "ERROR")
        return
    
    if current_yes is None:
        log("Could not get current price", "ERROR")
        return
    
    # Calculate and execute sell
    current_no = 1 - current_yes
    if pos.bet_side == "NO":
        current_price = current_no
    else:
        current_price = current_yes
    
    sale_value = current_price * pos.shares
    exit_fee = sale_value * portfolio.entry_cost_rate
    pnl = (sale_value - exit_fee) - pos.size_usd
    
    log(f"Entry: {pos.entry_price:.1%} | Current: {current_price:.1%} | P&L: ${pnl:+.2f}")
    
    # Update position
    pos.status = "closed"
    pos.close_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    pos.resolution = "win" if pnl > 0 else "lose"
    pos.pnl = pnl
    pos.current_price = current_price
    pos.price_yes_current = current_yes
    
    # Move to closed trades
    portfolio.closed_trades.append(pos)
    
    # Update stats
    pt.update_portfolio_stats(portfolio)
    pt.save_portfolio(portfolio, portfolio_file)
    
    log(f"✅ Position sold! New bankroll: ${portfolio.bankroll_current:.2f}")


# =============================================================================
# LIVE TRADING (placeholder)
# =============================================================================

def run_bot(dry_run: bool = True, scan_only: bool = False):
    """Main bot execution for live trading."""
    run_start = datetime.now()
    log("=" * 60)
    log("POLYMARKET BOT STARTED")
    log(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}{' (scan only)' if scan_only else ''}")
    log("=" * 60)
    
    run_stats = {
        "timestamp": run_start.isoformat(),
        "mode": "dry_run" if dry_run else "live",
        "markets_scanned": 0,
        "candidates_found": 0,
        "trades_selected": 0,
        "trades_executed": 0,
        "errors": [],
    }
    
    try:
        # 1. Get account balance
        log("Fetching account balance...")
        balance = api.get_account_balance()
        if balance is None:
            balance = config.BANKROLL
        log(f"Available balance: ${balance:.2f}")
        
        # 2. Get current positions
        log("Fetching current positions...")
        positions = api.get_open_positions()
        existing_ids = {p.get("market_id", p.get("marketId", "")) for p in positions}
        
        current_exposure, exposure_by_cluster = strategy.calculate_exposure(positions)
        log(f"Current exposure: ${current_exposure:.2f} ({len(positions)} positions)")
        
        # 3. Fetch open markets
        log("Fetching open markets...")
        markets = api.fetch_open_markets(limit=5000)
        run_stats["markets_scanned"] = len(markets)
        log(f"Found {len(markets)} open markets")
        
        current_ts = datetime.now().timestamp()
        
        # === SAVE SNAPSHOT ===
        log("\n--- SAVING SNAPSHOT ---")
        save_run_snapshot(markets, current_ts, len(markets))
        
        # 4. Evaluate each market
        log("Evaluating markets...")
        candidates = []
        
        for market in markets:
            timestamps = api.parse_market_timestamps(market)
            tokens = api.get_token_ids(market)
            
            candidate = strategy.evaluate_market(
                market, timestamps, tokens, current_ts
            )
            
            if candidate:
                candidates.append(candidate)
        
        run_stats["candidates_found"] = len(candidates)
        log(f"Found {len(candidates)} qualifying candidates")
        
        # 5. Show all candidates
        if candidates:
            log("-" * 60)
            log("CANDIDATES:")
            for c in sorted(candidates, key=lambda x: x.volume, reverse=True)[:20]:
                log(f"  {strategy.format_candidate_summary(c)}")
            if len(candidates) > 20:
                log(f"  ... and {len(candidates) - 20} more")
            log("-" * 60)
        
        if scan_only:
            log("Scan only mode - stopping here")
            return run_stats
        
        # 6. Select trades
        log("Selecting trades...")
        cash_available = balance - current_exposure
        
        selected = strategy.select_trades(
            candidates=candidates,
            cash_available=cash_available,
            current_exposure=current_exposure,
            exposure_by_cluster=exposure_by_cluster,
            bankroll=config.BANKROLL,
            existing_market_ids=existing_ids,
        )
        
        run_stats["trades_selected"] = len(selected)
        log(f"Selected {len(selected)} trades to execute")
        
        # 7. Execute trades
        for trade in selected:
            log(f"\nExecuting: {strategy.format_candidate_summary(trade)}")
            
            if dry_run:
                log("  [DRY RUN] Would place order")
                run_stats["trades_executed"] += 1
            else:
                # Real trading logic here
                pass
        
        # Save run history
        save_run_history(run_stats)
        
        # Telegram notification
        if run_stats["trades_executed"] > 0:
            msg = (
                f"🤖 <b>Bot Run Complete</b>\n"
                f"Markets scanned: {run_stats['markets_scanned']}\n"
                f"Candidates: {run_stats['candidates_found']}\n"
                f"Trades: {run_stats['trades_executed']}"
            )
            send_telegram(msg)
        
    except Exception as e:
        log(f"Error: {e}", "ERROR")
        run_stats["errors"].append(str(e))
        import traceback
        traceback.print_exc()
    
    return run_stats


# =============================================================================
# CLI
# =============================================================================

def print_help():
    """Print help message."""
    print(__doc__)


def main():
    args = sys.argv[1:]
    
    if not args or args[0] in ["-h", "--help", "help"]:
        print_help()
        return
    
    if args[0] in ["--strategies", "-s", "strategies"]:
        import strategies as strat_config
        strat_config.print_strategies()
        return
    
    if args[0] == "--paper":
        strategy_name = None
        if len(args) > 1:
            if args[1] in ["--strategy", "-s"] and len(args) > 2:
                strategy_name = args[2]
            else:
                strategy_name = args[1]
        run_paper_trading(strategy_name)
        return
    
    if args[0] == "--sell":
        if len(args) < 2:
            log("Usage: python bot.py --sell <search_term>", "ERROR")
            return
        manual_sell(args[1])
        return
    
    if args[0] == "--scan-only":
        run_bot(dry_run=True, scan_only=True)
        return
    
    if args[0] == "--live":
        print("⚠️  LIVE TRADING MODE")
        print("This will place REAL orders with REAL money!")
        confirm = input("Type 'CONFIRM' to proceed: ")
        if confirm.strip() == "CONFIRM":
            run_bot(dry_run=False)
        else:
            print("Cancelled")
        return
    
    # Default: dry run
    run_bot(dry_run=True)


if __name__ == "__main__":
    main()
