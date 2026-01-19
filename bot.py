#!/usr/bin/env python3
"""
POLYMARKET BOT - Main Entry Point
==================================
Runs the trading strategy and places orders.

Usage:
    python bot.py                    # Dry run (default)
    python bot.py --live             # Live trading (real orders)
    python bot.py --scan-only        # Just scan markets, no orders
    python bot.py --paper            # Paper trading - ALL strategies
    python bot.py --paper balanced   # Paper trading - single strategy
    python bot.py --help             # Show available strategies

Strategies:
    conservative  - NO 10-25%, high win rate, low risk
    balanced      - NO 20-60%, baseline strategy
    aggressive    - NO 30-60%, higher risk/reward
    volume_sweet  - NO 20-60%, 15k-100k volume only
"""

import sys
import json
from datetime import datetime
from typing import Dict, List, Any

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
        
        # Keep last 100 runs
        history = history[-100:]
        
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
        import requests
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
# MAIN BOT LOGIC
# =============================================================================

def run_bot(dry_run: bool = True, scan_only: bool = False):
    """Main bot execution."""
    
    run_start = datetime.now()
    log("=" * 60)
    log("POLYMARKET BOT STARTED")
    log(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}{' (scan only)' if scan_only else ''}")
    log("=" * 60)
    
    # Track run stats
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
            balance = config.BANKROLL  # Fallback for dry run
        log(f"Available balance: ${balance:.2f}")
        
        # 2. Get current positions
        log("Fetching current positions...")
        positions = api.get_open_positions()
        existing_ids = {p.get("market_id", p.get("marketId", "")) for p in positions}
        
        current_exposure, exposure_by_cluster = strategy.calculate_exposure(positions)
        log(f"Current exposure: ${current_exposure:.2f} ({len(positions)} positions)")
        for cluster, exp in exposure_by_cluster.items():
            log(f"  {cluster}: ${exp:.2f}")
        
        # 3. Fetch open markets
        log("Fetching open markets...")
        markets = api.fetch_open_markets(limit=1000)
        run_stats["markets_scanned"] = len(markets)
        log(f"Found {len(markets)} open markets")
        
        # 4. Evaluate each market
        log("Evaluating markets...")
        current_ts = datetime.now().timestamp()
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
        
        # 6. Select trades based on constraints
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
        if selected:
            log("-" * 60)
            log("EXECUTING TRADES:")
            
            notification_lines = [f"🤖 <b>Polymarket Bot Run</b>"]
            notification_lines.append(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
            notification_lines.append(f"Trades: {len(selected)}")
            notification_lines.append("")
            
            for trade in selected:
                log(f"  Placing {trade.bet_side} order: ${config.BET_SIZE:.2f}")
                log(f"    Market: {trade.question[:60]}...")
                log(f"    Token: {trade.token_id}")
                log(f"    Price: {trade.price_entry:.2%}")
                
                result = api.place_market_order(
                    token_id=trade.token_id,
                    side="BUY",  # We're buying the NO token
                    size=config.BET_SIZE,
                    dry_run=dry_run
                )
                
                if result:
                    run_stats["trades_executed"] += 1
                    status = "✅" if not dry_run else "🔸 (dry)"
                else:
                    status = "❌ FAILED"
                    run_stats["errors"].append(f"Failed to place order for {trade.market_id}")
                
                notification_lines.append(
                    f"{status} {trade.bet_side} ${config.BET_SIZE:.0f} @ {trade.price_entry:.0%}\n"
                    f"   {trade.question[:40]}..."
                )
                
                log(f"    Result: {status}")
            
            # Send notification
            send_telegram("\n".join(notification_lines))
        
        else:
            log("No trades to execute")
            send_telegram(f"🤖 Polymarket Bot: No trades this run\n{len(candidates)} candidates, none selected")
    
    except Exception as e:
        log(f"Bot error: {e}", "ERROR")
        run_stats["errors"].append(str(e))
        send_telegram(f"🚨 Polymarket Bot ERROR:\n{str(e)}")
        raise
    
    finally:
        # Save run history
        save_run_history(run_stats)
        
        run_duration = (datetime.now() - run_start).total_seconds()
        log("=" * 60)
        log(f"BOT RUN COMPLETE in {run_duration:.1f}s")
        log(f"  Markets scanned: {run_stats['markets_scanned']}")
        log(f"  Candidates: {run_stats['candidates_found']}")
        log(f"  Trades executed: {run_stats['trades_executed']}")
        log("=" * 60)
    
    return run_stats


# =============================================================================
# PAPER TRADING
# =============================================================================

def run_paper_trading(strategy_name: str = None):
    """Run paper trading mode - simulated trading with persistence.
    
    Args:
        strategy_name: Name of strategy to run (from strategies.py), or None to run all
    """
    import paper_trading as pt
    import strategies as strat_config
    
    run_start = datetime.now()
    log("=" * 60)
    log("POLYMARKET BOT - PAPER TRADING MODE")
    log("=" * 60)
    
    # Determine which strategies to run
    if strategy_name:
        if strategy_name not in strat_config.STRATEGIES:
            log(f"ERROR: Unknown strategy '{strategy_name}'", "ERROR")
            log(f"Available: {list(strat_config.STRATEGIES.keys())}")
            return
        strategies_to_run = {strategy_name: strat_config.STRATEGIES[strategy_name]}
    else:
        strategies_to_run = strat_config.STRATEGIES
    
    log(f"Running {len(strategies_to_run)} strategies: {list(strategies_to_run.keys())}")
    
    # Fetch all markets once (shared across strategies)
    log("\nFetching markets...")
    markets = api.fetch_open_markets(limit=5000)
    log(f"Found {len(markets)} markets")
    
    # Build market lookup
    market_lookup = {m.get("id") or m.get("conditionId"): m for m in markets}
    current_ts = datetime.now().timestamp()
    
    # Prepare summary for Telegram
    summary_lines = [f"📊 <b>Paper Trading Update</b>", f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    
    # Run each strategy
    for strat_name, strat_params in strategies_to_run.items():
        log("\n" + "=" * 60)
        log(f"STRATEGY: {strat_params['name']}")
        log("=" * 60)
        
        portfolio_file = strat_params.get("portfolio_file", f"portfolio_{strat_name}.json")
        initial_bankroll = strat_params.get("bankroll", 1500.0)
        
        # Load portfolio for this strategy
        portfolio = pt.load_portfolio(
            portfolio_file=portfolio_file,
            initial_bankroll=initial_bankroll,
            entry_cost_rate=strat_params.get("entry_cost_rate", 0.03),
        )
        
        # 1) Check resolutions of open positions
        log("Checking open positions for resolutions...")
        open_positions = [p for p in portfolio.positions if p.status == "open"]
        newly_closed = 0
        
        for pos in open_positions:
            market_data = market_lookup.get(pos.market_id)
            
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
        
        for market in markets:
            timestamps = api.parse_market_timestamps(market)
            tokens = api.get_token_ids(market)
            
            candidate = strategy.evaluate_market(
                market, timestamps, tokens, current_ts,
                strategy_params=strat_params,
            )
            
            if candidate:
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
        
        # 4) Save portfolio
        pt.save_portfolio(portfolio, portfolio_file)
        
        # 5) Print summary
        pt.print_portfolio_summary(portfolio, strat_params['name'])
        
        # Add to Telegram summary
        open_count = len([p for p in portfolio.positions if p.status == "open"])
        roi_pct = portfolio.total_pnl / portfolio.bankroll_initial * 100
        win_rate = (portfolio.wins / len(portfolio.closed_trades) * 100) if portfolio.closed_trades else 0
        
        summary_lines.append(f"<b>{strat_params['name']}</b>")
        summary_lines.append(f"  P&L: ${portfolio.total_pnl:+.2f} ({roi_pct:+.1f}%)")
        summary_lines.append(f"  Win rate: {win_rate:.0f}% | Open: {open_count}")
        summary_lines.append("")
    
    # Send Telegram summary
    send_telegram("\n".join(summary_lines))
    
    run_duration = (datetime.now() - run_start).total_seconds()
    log(f"\nPaper trading run complete in {run_duration:.1f}s")


# =============================================================================
# CLI
# =============================================================================

def main():
    dry_run = True
    scan_only = False
    paper_mode = False
    paper_strategy = None  # None = run all strategies
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--live":
            dry_run = False
        elif arg == "--scan-only":
            scan_only = True
        elif arg == "--paper":
            paper_mode = True
            # Check if next arg is a strategy name
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                paper_strategy = args[i + 1]
                i += 1
        elif arg == "--help":
            print(__doc__)
            print("\nStrategies available for --paper:")
            import strategies
            for name, strat in strategies.STRATEGIES.items():
                print(f"  {name}: {strat['description']}")
            sys.exit(0)
        i += 1
    
    if paper_mode:
        run_paper_trading(paper_strategy)
        return
    
    # Safety check for live mode
    if not dry_run:
        log("⚠️  LIVE MODE - Real orders will be placed!", "WARN")
        if not config.POLYMARKET_API_KEY:
            log("ERROR: POLYMARKET_API_KEY not set", "ERROR")
            sys.exit(1)
        
        # Require explicit confirmation
        confirm = input("Type 'CONFIRM' to proceed with live trading: ")
        if confirm != "CONFIRM":
            log("Aborted")
            sys.exit(0)
    
    run_bot(dry_run=dry_run, scan_only=scan_only)


if __name__ == "__main__":
    main()
