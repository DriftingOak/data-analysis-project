#!/usr/bin/env python3
"""
POLYMARKET BOT - Main Entry Point
==================================
Runs the trading strategy and places orders.

Usage:
    python bot.py              # Dry run (default)
    python bot.py --live       # Live trading (real orders)
    python bot.py --scan-only  # Just scan markets, no orders
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
# CLI
# =============================================================================

def main():
    dry_run = True
    scan_only = False
    
    for arg in sys.argv[1:]:
        if arg == "--live":
            dry_run = False
        elif arg == "--scan-only":
            scan_only = True
        elif arg == "--help":
            print(__doc__)
            sys.exit(0)
    
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
