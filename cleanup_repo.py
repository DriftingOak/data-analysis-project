#!/usr/bin/env python3
"""
CLEANUP SCRIPT — Remove live trading code from GitHub repo
============================================================
Run this from the root of your polymarket-bot repo.

What it does:
1. Deletes live trading files (live_trading.py, execute.yml, etc.)
2. Removes PRIVATE_KEY/PROXY_ADDRESS refs from run.yml
3. Removes live strategy from strategies.py
4. Cleans up backup files
5. Updates .gitignore

After running:
    git add -A
    git commit -m "Remove live trading code (moved to local)"
    git push

Also remember to DELETE these GitHub Secrets (Settings → Secrets):
    - PRIVATE_KEY
    - POLYMARKET_PROXY_ADDRESS
    - LIVE_TRADING_ENABLED
    - LIVE_SHADOW_MODE
"""

import os
import sys
import shutil

def log(msg, level="INFO"):
    emoji = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "DEL": "🗑️"}
    print(f"  {emoji.get(level, '•')} {msg}")

def delete_file(path):
    if os.path.exists(path):
        os.remove(path)
        log(f"Deleted: {path}", "DEL")
    else:
        log(f"Already gone: {path}", "OK")

def delete_dir(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
        log(f"Deleted dir: {path}", "DEL")

def main():
    # Check we're in the right place
    if not os.path.exists("bot.py"):
        print("❌ Run this from the root of your polymarket-bot repo!")
        sys.exit(1)

    print("=" * 60)
    print("CLEANING LIVE TRADING FROM GITHUB REPO")
    print("=" * 60)

    # ── 1. Delete live trading files ─────────────────────────────
    print("\n1. Removing live trading files...")
    files_to_delete = [
        "live_trading.py",
        "test_live_setup.py",
        "apply_live_patches.py",
        "INTEGRATION_GUIDE.py",
        ".github/workflows/execute.yml",
        "pending_trades.json",
        "live_portfolio.json",
    ]
    for f in files_to_delete:
        delete_file(f)

    # ── 2. Delete backup files ───────────────────────────────────
    print("\n2. Removing backup files...")
    import glob
    for pattern in ["*.backup-*", "*.bak"]:
        for f in glob.glob(pattern):
            delete_file(f)

    # ── 3. Clean run.yml ─────────────────────────────────────────
    print("\n3. Cleaning run.yml...")
    workflow_path = ".github/workflows/run.yml"
    if os.path.exists(workflow_path):
        with open(workflow_path) as f:
            content = f.read()

        # Remove live-related env vars
        lines_to_remove = [
            "          PRIVATE_KEY: ${{ secrets.PRIVATE_KEY }}",
            "          POLYMARKET_PROXY_ADDRESS: ${{ secrets.POLYMARKET_PROXY_ADDRESS }}",
            "          LIVE_TRADING_ENABLED: ${{ secrets.LIVE_TRADING_ENABLED }}",
            "          LIVE_SHADOW_MODE: ${{ secrets.LIVE_SHADOW_MODE }}",
        ]
        for line in lines_to_remove:
            if line in content:
                content = content.replace(line + "\n", "")
                log(f"Removed env var from run.yml", "OK")

        # Remove 'live' from strategy choices if present
        content = content.replace("          - live\n", "")

        # Remove git add of live files
        content = content.replace("          git add pending_trades.json || true\n", "")
        content = content.replace("          git add live_portfolio.json || true\n", "")

        with open(workflow_path, "w") as f:
            f.write(content)
        log("run.yml cleaned", "OK")

    # ── 4. Clean strategies.py ───────────────────────────────────
    print("\n4. Cleaning strategies.py...")
    strat_path = "strategies.py"
    if os.path.exists(strat_path):
        with open(strat_path) as f:
            content = f.read()

        # Remove test_live strategy (if present as a block)
        if 'STRATEGIES["test_live"]' in content:
            # Find and remove the entire test_live block
            start = content.find('STRATEGIES["test_live"]')
            if start != -1:
                # Find next STRATEGIES[ or end of section
                end = content.find('\nSTRATEGIES["', start + 1)
                if end == -1:
                    end = content.find('\n# ===', start + 1)
                if end == -1:
                    end = content.find('\nSTRATEGY_GROUPS', start)
                if end != -1:
                    content = content[:start] + content[end:]
                    log("Removed test_live strategy", "OK")

        # Remove 'live' group reference
        content = content.replace('    "live": ["test_live"],\n', "")

        # Remove mode fields from remaining strategies
        content = content.replace('        "mode": "paper",  # "paper" or "live"\n', "")
        content = content.replace('    "mode": "paper",  # "paper" or "live"\n', "")

        with open(strat_path, "w") as f:
            f.write(content)
        log("strategies.py cleaned", "OK")

    # ── 5. Clean config.py ───────────────────────────────────────
    print("\n5. Cleaning config.py...")
    config_path = "config.py"
    if os.path.exists(config_path):
        with open(config_path) as f:
            content = f.read()

        # Remove PRIVATE_KEY and PROXY_ADDRESS if they're env reads
        lines_to_clean = [
            'PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")',
            'POLYMARKET_PROXY_ADDRESS = os.getenv("POLYMARKET_PROXY_ADDRESS", "")',
            'LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false")',
            'LIVE_SHADOW_MODE = os.getenv("LIVE_SHADOW_MODE", "false")',
        ]
        for line in lines_to_clean:
            if line in content:
                content = content.replace(line + "\n", "")
                log(f"Removed from config.py: {line[:40]}...", "OK")

        with open(config_path, "w") as f:
            f.write(content)

    # ── 6. Update .gitignore ─────────────────────────────────────
    print("\n6. Updating .gitignore...")
    gitignore_path = ".gitignore"
    additions = [
        "# Never commit secrets",
        ".env",
        "*.backup-*",
        "live_portfolio.json",
        "pending_trades.json",
    ]
    existing = ""
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            existing = f.read()

    with open(gitignore_path, "a") as f:
        for line in additions:
            if line not in existing:
                f.write(line + "\n")
                log(f"Added to .gitignore: {line}", "OK")

    # ── 7. Clean requirements.txt ────────────────────────────────
    print("\n7. Cleaning requirements.txt...")
    req_path = "requirements.txt"
    if os.path.exists(req_path):
        with open(req_path) as f:
            lines = f.readlines()
        cleaned = [l for l in lines if "py-clob-client" not in l and "web3" not in l]
        with open(req_path, "w") as f:
            f.writelines(cleaned)
        log("Removed py-clob-client and web3 from requirements.txt", "OK")

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("DONE! Next steps:")
    print("=" * 60)
    print("""
1. Review changes:
   git status
   git diff

2. Commit and push:
   git add -A
   git commit -m "Remove live trading code (moved to local)"
   git push

3. DELETE these GitHub Secrets (Settings → Secrets → Actions):
   - PRIVATE_KEY          ← CRITICAL: remove this!
   - POLYMARKET_PROXY_ADDRESS
   - LIVE_TRADING_ENABLED
   - LIVE_SHADOW_MODE

4. Keep these secrets (still needed for paper trading API):
   - POLYMARKET_API_KEY
   - POLYMARKET_SECRET
   - POLYMARKET_PASSPHRASE
   - TELEGRAM_BOT_TOKEN   (if you want paper trading alerts)
   - TELEGRAM_CHAT_ID
""")


if __name__ == "__main__":
    main()
