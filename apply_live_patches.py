#!/usr/bin/env python3
"""
APPLY LIVE TRADING PATCHES
============================
Run this script from your repo root to apply live trading modifications
to bot.py, strategies.py, and config.py.

Usage:
    cd /path/to/polymarket-bot
    python apply_live_patches.py

What it does:
    1. Adds POLYMARKET_PROXY_ADDRESS + live settings to config.py
    2. Adds "mode" field support to strategies.py
    3. Adds live trading integration to bot.py
    4. Updates requirements.txt with py-clob-client

It creates backups before modifying any file.
"""

import os
import shutil
import re
from datetime import datetime

BACKUP_SUFFIX = f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

def backup(filepath):
    """Create a backup of a file."""
    if os.path.exists(filepath):
        backup_path = filepath + BACKUP_SUFFIX
        shutil.copy2(filepath, backup_path)
        print(f"  📋 Backed up: {filepath} → {backup_path}")

def read_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def write_file(filepath, content):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

# =============================================================================
# PATCH 1: config.py
# =============================================================================

def patch_config():
    """Add POLYMARKET_PROXY_ADDRESS and live trading settings."""
    filepath = "config.py"
    if not os.path.exists(filepath):
        print(f"  ❌ {filepath} not found")
        return False
    
    backup(filepath)
    content = read_file(filepath)
    
    # Add POLYMARKET_PROXY_ADDRESS after PRIVATE_KEY
    if "POLYMARKET_PROXY_ADDRESS" not in content:
        content = content.replace(
            'PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")',
            'PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")\n\n'
            '# Polymarket proxy address (for browser wallet / signature_type=2)\n'
            '# Find it: polymarket.com → Deposit → Deposit Address\n'
            'POLYMARKET_PROXY_ADDRESS = os.getenv("POLYMARKET_PROXY_ADDRESS", "")'
        )
        print("  ✅ Added POLYMARKET_PROXY_ADDRESS")
    else:
        print("  ⏭  POLYMARKET_PROXY_ADDRESS already exists")
    
    # Add live trading settings before keywords section
    if "LIVE_TRADING_ENABLED" not in content:
        live_settings = '''
# =============================================================================
# LIVE TRADING SETTINGS
# =============================================================================

# Master switch: must be "true" to execute real trades
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

# Shadow mode: runs full pipeline but doesn't place orders  
LIVE_SHADOW_MODE = os.getenv("LIVE_SHADOW_MODE", "false").lower() == "true"

'''
        # Insert before KEYWORDS section
        if "KEYWORDS" in content:
            content = content.replace(
                "# =============================================================================\n# KEYWORDS",
                live_settings + "# =============================================================================\n# KEYWORDS"
            )
        else:
            content += "\n" + live_settings
        print("  ✅ Added LIVE_TRADING settings")
    else:
        print("  ⏭  LIVE_TRADING settings already exist")
    
    write_file(filepath, content)
    return True


# =============================================================================
# PATCH 2: strategies.py
# =============================================================================

def patch_strategies():
    """Ensure all strategies have a 'mode' field (default: 'paper')."""
    filepath = "strategies.py"
    if not os.path.exists(filepath):
        print(f"  ❌ {filepath} not found")
        return False
    
    backup(filepath)
    content = read_file(filepath)
    
    if '"mode"' in content:
        print("  ⏭  Strategies already have 'mode' field")
        return True
    
    # Add mode="paper" to each strategy definition after the "name" line
    # Pattern: after "name": "...", add "mode": "paper",
    pattern = r'("name":\s*"[^"]+",)'
    replacement = r'\1\n        "mode": "paper",  # "paper" or "live"'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        write_file(filepath, new_content)
        print("  ✅ Added 'mode': 'paper' to all strategies")
    else:
        print("  ⚠️  Could not auto-patch strategies.py — add 'mode' manually")
    
    return True


# =============================================================================
# PATCH 3: bot.py
# =============================================================================

def patch_bot():
    """Add live trading integration to bot.py."""
    filepath = "bot.py"
    if not os.path.exists(filepath):
        print(f"  ❌ {filepath} not found")
        return False
    
    backup(filepath)
    content = read_file(filepath)
    
    changes_made = 0
    
    # 3a. Add import
    if "import live_trading" not in content:
        # Add after existing imports
        import_line = "\n# Live trading integration\ntry:\n    import live_trading as lt\n    HAS_LIVE_TRADING = True\nexcept ImportError:\n    HAS_LIVE_TRADING = False\n"
        
        if "import strategy" in content:
            content = content.replace(
                "import strategy",
                "import strategy" + import_line
            )
            changes_made += 1
            print("  ✅ Added live_trading import")
    else:
        print("  ⏭  live_trading import already exists")
    
    # 3b. Add --live-status command
    if "--live-status" not in content:
        # Add before the default dry run at the end of main()
        live_status_block = '''
    if args[0] == "--live-status":
        if HAS_LIVE_TRADING:
            lt.print_live_status()
        else:
            print("live_trading module not available")
        return
    
'''
        # Insert after --sell command handler
        if '"--sell"' in content:
            content = content.replace(
                '    if args[0] == "--sell":',
                live_status_block + '    if args[0] == "--sell":'
            )
            changes_made += 1
            print("  ✅ Added --live-status command")
    else:
        print("  ⏭  --live-status command already exists")
    
    # 3c. Add live resolution check at start of run_paper_trading
    if "check_live_resolutions" not in content:
        resolution_check = '''
    # === CHECK LIVE POSITION RESOLUTIONS ===
    if HAS_LIVE_TRADING:
        try:
            market_lookup_live = {m.get("id", m.get("market_id", "")): m for m in markets}
            resolved = lt.check_live_resolutions(market_lookup_live)
            if resolved > 0:
                log(f"🔔 {resolved} live positions resolved")
            expired = lt.cleanup_expired_proposals()
            if expired > 0:
                log(f"🧹 Cleaned up {expired} expired proposals")
        except Exception as e:
            log(f"Live resolution check: {e}", "WARN")
    
'''
        # Insert after market_lookup creation
        if "market_lookup" in content and "for strat_name, strat_params" in content:
            # Find the line before the strategy loop
            content = content.replace(
                "    for strat_name, strat_params in strategies_to_run.items():",
                resolution_check + "    for strat_name, strat_params in strategies_to_run.items():"
            )
            changes_made += 1
            print("  ✅ Added live resolution check")
    else:
        print("  ⏭  Live resolution check already exists")
    
    # 3d. Add mode-aware trade execution
    # This is the trickiest part - replace the paper_buy loop
    if "propose_trade" not in content:
        # Find the paper_buy execution block and wrap it in a mode check
        old_paper_buy = '''        # Execute paper trades
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
            )'''
        
        new_trade_execution = '''        # Execute trades (paper or live propose depending on strategy mode)
        strategy_mode = strat_params.get("mode", "paper")
        live_proposals = []
        
        for trade in selected:
            expected_close = datetime.fromtimestamp(trade.end_ts).strftime("%Y-%m-%d")
            
            # Always record as paper trade (for comparison tracking)
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
            
            # If live mode: also propose for real execution
            if strategy_mode == "live" and HAS_LIVE_TRADING:
                try:
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
                except Exception as e:
                    log(f"Failed to propose live trade: {e}", "ERROR")'''
        
        if old_paper_buy in content:
            content = content.replace(old_paper_buy, new_trade_execution)
            changes_made += 1
            print("  ✅ Added mode-aware trade execution")
        else:
            print("  ⚠️  Could not find exact paper_buy block to patch")
            print("     You'll need to manually add live trade proposal logic")
            print("     See INTEGRATION_GUIDE.py for the code to add")
    else:
        print("  ⏭  Live trade proposal already exists")
    
    # 3e. Update the log line for trades
    if "📝" in content and "🔔 PROPOSED" not in content:
        old_log = '            log(f"  📝 {trade.bet_side} @ {trade.price_entry:.1%} | [{trade.cluster}] {trade.question[:40]}...")'
        new_log = '''            emoji = "🔔" if (strategy_mode == "live" and HAS_LIVE_TRADING) else "📝"
            log(f"  {emoji} {trade.bet_side} @ {trade.price_entry:.1%} | [{trade.cluster}] {trade.question[:40]}...")'''
        
        if old_log in content:
            content = content.replace(old_log, new_log)
            changes_made += 1
            print("  ✅ Updated trade log emoji for live mode")
    
    # 3f. Add live proposals count to summary
    if "live_proposals" not in content and "summary_lines" in content:
        old_summary = '        summary_lines.append('
        # Only patch the first occurrence if it's the strategy summary
        pass  # Skip this for now, it's cosmetic
    
    if changes_made > 0:
        write_file(filepath, content)
    
    return True


# =============================================================================
# PATCH 4: requirements.txt
# =============================================================================

def patch_requirements():
    """Add py-clob-client to requirements.txt."""
    filepath = "requirements.txt"
    
    if not os.path.exists(filepath):
        write_file(filepath, "requests\npy-clob-client\nweb3==6.14.0\n")
        print("  ✅ Created requirements.txt with py-clob-client")
        return True
    
    backup(filepath)
    content = read_file(filepath)
    
    additions = []
    if "py-clob-client" not in content:
        additions.append("py-clob-client")
    if "web3" not in content:
        additions.append("web3==6.14.0")
    
    if additions:
        content = content.rstrip() + "\n" + "\n".join(additions) + "\n"
        write_file(filepath, content)
        print(f"  ✅ Added to requirements.txt: {', '.join(additions)}")
    else:
        print("  ⏭  requirements.txt already has py-clob-client")
    
    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("APPLYING LIVE TRADING PATCHES")
    print("=" * 60)
    
    # Check we're in the right directory
    if not os.path.exists("bot.py"):
        print("\n❌ bot.py not found in current directory.")
        print("   Run this script from your polymarket-bot repo root.")
        return
    
    print("\n1. Patching config.py...")
    patch_config()
    
    print("\n2. Patching strategies.py...")
    patch_strategies()
    
    print("\n3. Patching bot.py...")
    patch_bot()
    
    print("\n4. Patching requirements.txt...")
    patch_requirements()
    
    # Check for new files
    print("\n5. Checking new files...")
    new_files = {
        "live_trading.py": "Core live trading module",
        "test_live_setup.py": "Setup verification script",
        ".github/workflows/execute.yml": "Trade execution workflow",
    }
    
    for f, desc in new_files.items():
        if os.path.exists(f):
            print(f"  ✅ {f} exists ({desc})")
        else:
            print(f"  ❌ {f} MISSING — copy it from the files Claude gave you")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("""
1. Copy these new files to your repo (if not already done):
   - live_trading.py
   - test_live_setup.py
   - .github/workflows/execute.yml

2. Add GitHub Secret:
   POLYMARKET_PROXY_ADDRESS → your Polymarket deposit address

3. Test locally:
   export PRIVATE_KEY="0x..."
   export POLYMARKET_PROXY_ADDRESS="0x..."
   python test_live_setup.py

4. Start in shadow mode:
   - In strategies.py, set one strategy to "mode": "live"
   - Set LIVE_SHADOW_MODE=true in GitHub Secrets
   - Push and let the bot run

5. When ready for real trading:
   - Set LIVE_TRADING_ENABLED=true in GitHub Secrets
   - Set LIVE_SHADOW_MODE=false
   - Wait for Telegram proposal → approve via GitHub Actions
""")


if __name__ == "__main__":
    main()
