#!/usr/bin/env python3
"""
POLYMARKET BOT - Main Entry Point
==================================
Runs the trading strategy and places orders.

MODIFIÉ: Les snapshots sont maintenant gérés par un workflow séparé (snapshot.yml).
         Ce bot ne touche plus aux snapshots.

Usage:
    python bot.py                        # Dry run (default)
    python bot.py --live                 # Live trading (real orders)
    python bot.py --scan-only            # Just scan markets, no orders
    python bot.py --paper                # Paper trading - standard strategies
    python bot.py --paper balanced       # Paper trading - single strategy
    python bot.py --paper unlimited      # Paper trading - unlimited group
    python bot.py --paper all            # Paper trading - ALL strategies
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
# NOTE: SNAPSHOT INTEGRATION SUPPRIMÉE
# =============================================================================
# Les fonctions collect_all_eligible_markets() et save_run_snapshot() 
# ont été supprimées. Les snapshots sont maintenant gérés par:
#   - collect_snapshot.py (script standalone)
#   - .github/workflows/snapshot.yml (workflow séparé)
#
# Cela permet de:
#   1. Avoir des snapshots indépendants des bugs du bot
#   2. Utiliser des filtres différents (capture large vs trading strict)
#   3. Éviter les conflits Git entre workflows
# =============================================================================


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
    
    # NOTE: Snapshot sauvegarde supprimée - géré par workflow séparé
    # log("\n--- SAVING SNAPSHOT ---")
    # snapshot_path = save_run_snapshot(markets, current_ts, len(markets))
    
    # Prepare summary for Telegram
    summary_lines = [
        f"📊 <b>Paper Trading Update</b>",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ""
    ]
    
    # Run each strategy
    for strat_name, strat_params in strategies_to_run.items():
        log(f"\n{'='*60}")
        log(f"STRATEGY: {strat_name}")
        log(f"{'='*60}")
        
        try:
            # Get portfolio file for this strategy
            portfolio_file = strat_params.get("portfolio_file", f"portfolio_{strat_name}.json")
            portfolio_path = f"portfolios/{portfolio_file}"
            
            # Load or create portfolio
            portfolio = pt.load_portfolio(
                portfolio_file=portfolio_path,
                initial_bankroll=strat_params.get("bankroll", config.BANKROLL),
                entry_cost_rate=strat_params.get("entry_cost_rate", config.ENTRY_COST_RATE)
            )
            
            log(f"Portfolio: ${portfolio.bankroll_current:.2f} ({len(portfolio.positions)} positions)")
            
            # Update existing positions with current prices
            pt.update_positions(portfolio, market_lookup)
            
            # Check for resolved markets
            resolved = pt.check_resolutions(portfolio, market_lookup)
            if resolved:
                log(f"Resolved {len(resolved)} position(s)")
            
            # Get existing market IDs
            existing_ids = {p.market_id for p in portfolio.positions if p.status == "open"}
            
            # Calculate exposure
            exposure, cluster_exp = pt.calculate_exposure(portfolio)
            
            # Evaluate markets
            candidates = []
            for market in markets:
                timestamps = api.parse_market_timestamps(market)
                tokens = api.get_token_ids(market)
                
                candidate = strategy.evaluate_market(
                    market, timestamps, tokens, current_ts,
                    strategy_params=strat_params
                )
                
                if candidate:
                    # Check cluster filter if defined
                    cluster_filter = strat_params.get("cluster_filter")
                    if cluster_filter and candidate.cluster not in cluster_filter:
                        continue
                    candidates.append(candidate)
            
            log(f"Found {len(candidates)} candidates")
            
            # Select trades
            cash_available = portfolio.bankroll_current - exposure
            selected = strategy.select_trades(
                candidates=candidates,
                cash_available=cash_available,
                current_exposure=exposure,
                exposure_by_cluster=cluster_exp,
                bankroll=strat_params.get("bankroll", config.BANKROLL),
                existing_market_ids=existing_ids,
                max_exposure_pct=strat_params.get("max_total_exposure_pct", config.MAX_TOTAL_EXPOSURE_PCT),
                max_cluster_pct=strat_params.get("max_cluster_exposure_pct", config.MAX_CLUSTER_EXPOSURE_PCT),
                bet_size=strat_params.get("bet_size", config.BET_SIZE),
            )
            
            # Execute paper trades
            for trade in selected:
                pt.open_position(
                    portfolio=portfolio,
                    market_id=trade.market_id,
                    question=trade.question,
                    token_id=trade.token_id,
                    bet_side=trade.bet_side,
                    entry_price=trade.price_entry,
                    size_usd=strat_params.get("bet_size", config.BET_SIZE),
                    cluster=trade.cluster,
                    end_ts=trade.end_ts,
                )
                log(f"  PAPER BUY: {trade.bet_side} @ {trade.price_entry:.2f} - {trade.question[:50]}...")
            
            # Save portfolio
            pt.save_portfolio(portfolio, portfolio_path)
            
            # Add to summary
            open_positions = [p for p in portfolio.positions if p.status == "open"]
            summary_lines.append(
                f"<b>{strat_name}</b>: ${portfolio.bankroll_current:.0f} "
                f"({len(open_positions)} pos, {len(selected)} new)"
            )
            
        except Exception as e:
            log(f"Error running strategy {strat_name}: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            summary_lines.append(f"<b>{strat_name}</b>: ❌ Error")
    
    # Send Telegram summary
    if len(summary_lines) > 3:  # More than just header
        send_telegram("\n".join(summary_lines))
    
    log(f"\n{'='*60}")
    log(f"Paper trading complete in {(datetime.now() - run_start).seconds}s")
    log(f"{'='*60}")


# =============================================================================
# MANUAL SELL
# =============================================================================

def manual_sell(search_term: str):
    """Manually close positions matching search term."""
    import paper_trading as pt
    import strategies as strat_config
    
    log(f"Searching for positions matching: '{search_term}'")
    
    search_lower = search_term.lower()
    
    for strat_name, strat_params in strat_config.STRATEGIES.items():
        portfolio_file = strat_params.get("portfolio_file", f"portfolio_{strat_name}.json")
        portfolio_path = f"portfolios/{portfolio_file}"
        
        if not pt.os.path.exists(portfolio_path):
            continue
        
        portfolio = pt.load_portfolio(portfolio_path)
        
        # Find matching open positions
        matching = [
            p for p in portfolio.positions 
            if p.status == "open" and search_lower in p.question.lower()
        ]
        
        if not matching:
            continue
        
        log(f"\nFound {len(matching)} matching position(s) in {strat_name}:")
        for pos in matching:
            log(f"  - {pos.question[:60]}...")
            log(f"    Entry: {pos.entry_price:.2f}, Size: ${pos.size_usd:.2f}")
        
        confirm = input(f"\nClose these {len(matching)} position(s)? [y/N]: ")
        if confirm.lower() != 'y':
            log("Cancelled")
            continue
        
        # Mark as closed (as loss since manual)
        for pos in matching:
            pos.status = "closed"
            pos.resolution = "manual_close"
            pos.close_date = datetime.now().isoformat()
            pos.pnl = -pos.size_usd * 0.5  # Assume 50% loss on manual close
            
            portfolio.closed_trades.append(pos)
            portfolio.positions.remove(pos)
            portfolio.bankroll_current += pos.size_usd * 0.5  # Return half
        
        pt.save_portfolio(portfolio, portfolio_path)
        log(f"Closed {len(matching)} position(s)")
        log(f"New bankroll: ${portfolio.bankroll_current:.2f}")


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
        
        # NOTE: Snapshot sauvegarde supprimée - géré par workflow séparé
        # log("\n--- SAVING SNAPSHOT ---")
        # save_run_snapshot(markets, current_ts, len(markets))
        
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
        
        # 5. Select trades
        if scan_only:
            log("\n[SCAN ONLY] Would select from these candidates:")
            for c in candidates[:10]:
                log(f"  - {c.question[:60]}... @ {c.price_yes:.1%} YES")
            return
        
        cash_available = balance - current_exposure
        selected = strategy.select_trades(
            candidates=candidates,
            cash_available=cash_available,
            current_exposure=current_exposure,
            exposure_by_cluster=exposure_by_cluster,
            bankroll=balance,
            existing_market_ids=existing_ids,
        )
        
        run_stats["trades_selected"] = len(selected)
        log(f"Selected {len(selected)} trades to execute")
        
        # 6. Execute trades
        if not selected:
            log("No trades to execute")
        else:
            for trade in selected:
                log(f"\n{'DRY RUN: ' if dry_run else ''}Placing order:")
                log(f"  Market: {trade.question[:60]}...")
                log(f"  Side: {trade.bet_side}")
                log(f"  Price: {trade.price_entry:.4f}")
                log(f"  Size: ${config.BET_SIZE:.2f}")
                
                if not dry_run:
                    try:
                        order_result = api.place_order(
                            token_id=trade.token_id,
                            side="BUY",
                            price=trade.price_entry,
                            size=config.BET_SIZE,
                        )
                        if order_result:
                            run_stats["trades_executed"] += 1
                            log(f"  ✓ Order placed: {order_result.get('orderID', 'unknown')}")
                        else:
                            log("  ✗ Order failed", "ERROR")
                    except Exception as e:
                        log(f"  ✗ Order error: {e}", "ERROR")
                        run_stats["errors"].append(str(e))
        
        # 7. Save run history
        save_run_history(run_stats)
        
        # 8. Send notification
        if not dry_run and run_stats["trades_executed"] > 0:
            msg = (
                f"🤖 <b>Bot Execution Complete</b>\n"
                f"Scanned: {run_stats['markets_scanned']}\n"
                f"Candidates: {run_stats['candidates_found']}\n"
                f"Executed: {run_stats['trades_executed']}"
            )
            send_telegram(msg)
        
    except Exception as e:
        log(f"Bot error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        run_stats["errors"].append(str(e))
    
    log(f"\nBot finished in {(datetime.now() - run_start).seconds}s")


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
        strategy_name = args[1] if len(args) > 1 else None
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
