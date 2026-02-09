#!/usr/bin/env python3
"""
LIVE TRADING INTEGRATION GUIDE
================================
This file documents exactly what to change in bot.py and strategies.py
to support live trading alongside paper trading.

ARCHITECTURE:
    Same scan cycle → strategies with mode="paper" → paper_buy()
                    → strategies with mode="live"  → propose_trade() → Telegram
                    → Human approves on GitHub Actions → execute.yml → real order
"""

# =============================================================================
# 1. CHANGES TO strategies.py
# =============================================================================
"""
Add a "mode" field to each strategy. Default is "paper".
When you're ready to go live with a strategy, change it to "live".

Example - to put "balanced" live:

    "balanced": {
        "name": "Balanced",
        "mode": "live",           # ← ADD THIS LINE
        "bet_side": "NO",
        ...
    },

All other strategies keep "mode": "paper" (or omit it, defaults to "paper").
"""


# =============================================================================
# 2. CHANGES TO bot.py - Add import at top
# =============================================================================
"""
Add at the top of bot.py, with other imports:

    import live_trading as lt
"""


# =============================================================================
# 3. CHANGES TO bot.py - Modify run_paper_trading()
# =============================================================================
"""
In the run_paper_trading() function, after the trade selection loop,
replace the paper_buy execution block with a mode-aware dispatcher.

FIND this block (approximately):

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

REPLACE WITH:
"""

def _execute_trades_for_strategy(selected, portfolio, strat_name, strat_params, bet_size, pt):
    """Execute trades - either paper or live propose depending on strategy mode."""
    from datetime import datetime
    
    mode = strat_params.get("mode", "paper")
    live_proposals = []
    
    for trade in selected:
        expected_close = datetime.fromtimestamp(trade.end_ts).strftime("%Y-%m-%d")
        
        if mode == "live":
            # LIVE: Propose trade, don't execute
            proposal = lt.propose_trade(
                strategy=strat_name,
                market_id=trade.market_id,
                question=trade.question,
                token_id=trade.token_id,
                bet_side=trade.bet_side,
                proposed_price=trade.price_entry,
                size_usd=bet_size,
                cluster=trade.cluster,
                expected_close=expected_close,
            )
            lt.send_proposal_notification(proposal)
            live_proposals.append(proposal)
            
            print(f"  🔔 PROPOSED: {trade.bet_side} @ {trade.price_entry:.1%} "
                  f"| [{trade.cluster}] {trade.question[:40]}...")
            
            # ALSO record as paper trade for tracking comparison
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
        else:
            # PAPER: Execute as before
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
            
            print(f"  📝 {trade.bet_side} @ {trade.price_entry:.1%} "
                  f"| [{trade.cluster}] {trade.question[:40]}...")
    
    return live_proposals


# =============================================================================
# 4. CHANGES TO bot.py - Add live resolution check
# =============================================================================
"""
At the START of run_paper_trading(), after loading markets but before 
processing strategies, add:

    # Check live position resolutions (automatic, no approval needed)
    try:
        import live_trading as lt
        market_lookup_for_live = {m.get("id", m.get("market_id", "")): m for m in markets}
        resolved = lt.check_live_resolutions(market_lookup_for_live)
        if resolved > 0:
            log(f"🔔 {resolved} live positions resolved")
    except Exception as e:
        log(f"Live resolution check skipped: {e}", "WARN")

    # Cleanup expired proposals
    try:
        expired = lt.cleanup_expired_proposals()
        if expired > 0:
            log(f"Cleaned up {expired} expired proposals")
    except Exception as e:
        pass
"""


# =============================================================================
# 5. CHANGES TO bot.py - Add --live-status command
# =============================================================================
"""
In the main() function, add a new command:

    if args[0] == "--live-status":
        import live_trading as lt
        lt.print_live_status()
        return
"""


# =============================================================================
# 6. CHANGES TO run.yml - Add py-clob-client to dependencies
# =============================================================================
"""
In the "Install dependencies" step, add:

    pip install py-clob-client web3==6.14.0

And add the new env var:

    POLYMARKET_PROXY_ADDRESS: ${{ secrets.POLYMARKET_PROXY_ADDRESS }}
"""


# =============================================================================
# 7. NEW GITHUB SECRETS TO ADD
# =============================================================================
"""
Go to GitHub repo → Settings → Secrets and variables → Actions

Add:
    POLYMARKET_PROXY_ADDRESS   →  Your Polymarket deposit address (0x...)

Already should exist:
    PRIVATE_KEY                →  Your MetaMask private key (0x...)
    TELEGRAM_BOT_TOKEN         →  Telegram bot token
    TELEGRAM_CHAT_ID           →  Your Telegram chat ID
"""


# =============================================================================
# 8. DEPLOYMENT PHASES
# =============================================================================
"""
PHASE 1 — SHADOW MODE (no risk)
    - Set LIVE_SHADOW_MODE=true in GitHub Secrets
    - Change one strategy to mode="live"
    - Bot proposes trades, Telegram notifies, but nothing executes
    - Verify everything looks sane

PHASE 2 — FIRST REAL TRADE
    - Set LIVE_TRADING_ENABLED=true
    - Set LIVE_SHADOW_MODE=false
    - Wait for a proposal on Telegram
    - Go to GitHub Actions → Execute Live Trades → Run workflow
    - Enter the trade ID + type CONFIRM
    - Check polymarket.com to see the position

PHASE 3 — ROUTINE
    - Bot scans every 6h, proposes live trades via Telegram
    - You approve when convenient via GitHub Actions
    - Proposals expire after 6h if not approved (next scan repropose if still valid)
    - Resolutions happen automatically
"""
