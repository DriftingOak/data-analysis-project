#!/usr/bin/env python3
"""
LIVE TRADING SETUP VERIFICATION
================================
Run this script to verify your setup before going live.

Checks:
  1. py-clob-client installed
  2. Environment variables set
  3. CLOB API connection
  4. API credentials derivation
  5. Orderbook access
  6. Proxy address validation

Usage:
    # Set env vars first:
    export PRIVATE_KEY="0x..."
    export POLYMARKET_PROXY_ADDRESS="0x..."
    
    python test_live_setup.py
"""

import os
import sys

def check(name, passed, detail=""):
    emoji = "✅" if passed else "❌"
    print(f"  {emoji} {name}")
    if detail:
        print(f"     {detail}")
    return passed

def main():
    print("=" * 60)
    print("POLYMARKET LIVE TRADING - SETUP VERIFICATION")
    print("=" * 60 + "\n")
    
    all_ok = True
    
    # ── 1. Check py-clob-client ──────────────────────────────────
    print("1. Dependencies")
    print("-" * 40)
    
    try:
        import py_clob_client
        version = getattr(py_clob_client, "__version__", "unknown")
        all_ok &= check("py-clob-client installed", True, f"Version: {version}")
    except ImportError:
        all_ok &= check("py-clob-client installed", False, 
                        "Run: pip install py-clob-client web3==6.14.0")
    
    try:
        import web3
        all_ok &= check("web3 installed", True, f"Version: {web3.__version__}")
    except ImportError:
        all_ok &= check("web3 installed", False, 
                        "Run: pip install web3==6.14.0")
    
    # ── 2. Environment variables ─────────────────────────────────
    print("\n2. Environment Variables")
    print("-" * 40)
    
    private_key = os.getenv("PRIVATE_KEY", "")
    proxy_address = os.getenv("POLYMARKET_PROXY_ADDRESS", "")
    
    pk_ok = bool(private_key) and private_key.startswith("0x") and len(private_key) >= 64
    all_ok &= check("PRIVATE_KEY", pk_ok,
                    f"{'Set (starts with 0x...' + private_key[-4:] + ')' if pk_ok else 'Not set or invalid format'}")
    
    proxy_ok = bool(proxy_address) and proxy_address.startswith("0x") and len(proxy_address) == 42
    all_ok &= check("POLYMARKET_PROXY_ADDRESS", proxy_ok,
                    f"{proxy_address[:10]}...{proxy_address[-4:] if proxy_ok else 'Not set'}")
    
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    all_ok &= check("TELEGRAM_BOT_TOKEN", bool(tg_token),
                    "Set" if tg_token else "Not set (optional but recommended)")
    all_ok &= check("TELEGRAM_CHAT_ID", bool(tg_chat),
                    "Set" if tg_chat else "Not set (optional but recommended)")
    
    if not pk_ok or not proxy_ok:
        print("\n⚠️  Cannot proceed without PRIVATE_KEY and POLYMARKET_PROXY_ADDRESS")
        print("   Set them as environment variables or GitHub Secrets.\n")
        print("   To find your proxy address:")
        print("   1. Go to polymarket.com")
        print("   2. Connect MetaMask")
        print("   3. Click Deposit → your deposit address = proxy address")
        print("   4. Or go to https://reveal.polymarket.com")
        return False
    
    # ── 3. CLOB API Connection ───────────────────────────────────
    print("\n3. CLOB API Connection")
    print("-" * 40)
    
    try:
        from py_clob_client.client import ClobClient
        
        # Level 0: unauthenticated check
        client_anon = ClobClient("https://clob.polymarket.com")
        ok_resp = client_anon.get_ok()
        all_ok &= check("CLOB API reachable", ok_resp == "OK",
                        f"Response: {ok_resp}")
        
        server_time = client_anon.get_server_time()
        all_ok &= check("Server time", bool(server_time),
                        f"Server time: {server_time}")
        
    except Exception as e:
        all_ok &= check("CLOB API reachable", False, str(e))
        return False
    
    # ── 4. Authenticated Client ──────────────────────────────────
    print("\n4. Authenticated Client (signature_type=2)")
    print("-" * 40)
    
    try:
        client = ClobClient(
            "https://clob.polymarket.com",
            key=private_key,
            chain_id=137,
            signature_type=2,  # Browser wallet
            funder=proxy_address,
        )
        all_ok &= check("Client created", True)
        
        # Derive API credentials
        api_creds = client.create_or_derive_api_creds()
        has_creds = (
            hasattr(api_creds, 'api_key') and api_creds.api_key
        )
        all_ok &= check("API credentials derived", has_creds,
                        f"API key: {api_creds.api_key[:12]}..." if has_creds else "Failed")
        
        client.set_api_creds(api_creds)
        all_ok &= check("API credentials set", True)
        
    except Exception as e:
        all_ok &= check("Authenticated client", False, str(e))
        print("\n⚠️  Authentication failed. Common causes:")
        print("   - Wrong PRIVATE_KEY")
        print("   - Wrong POLYMARKET_PROXY_ADDRESS")
        print("   - Account not registered on Polymarket")
        return False
    
    # ── 5. Orderbook Access ──────────────────────────────────────
    print("\n5. Orderbook Access")
    print("-" * 40)
    
    try:
        # Find a live geopolitical market to test with
        import requests
        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"closed": "false", "limit": 20},
            timeout=10,
        )
        markets = resp.json()
        
        test_token = None
        test_question = None
        for m in markets:
            tokens_raw = m.get("clobTokenIds", "")
            if isinstance(tokens_raw, str):
                try:
                    import json
                    tokens = json.loads(tokens_raw)
                except:
                    tokens = []
            else:
                tokens = tokens_raw or []
            
            if len(tokens) >= 2:
                test_token = tokens[1]  # NO token
                test_question = m.get("question", "?")[:50]
                break
        
        if test_token:
            book = client.get_order_book(test_token)
            has_bids = len(book.get("bids", [])) > 0
            has_asks = len(book.get("asks", [])) > 0
            all_ok &= check("Orderbook fetch", True,
                           f"Market: {test_question}...")
            all_ok &= check("Orderbook has bids", has_bids,
                           f"{len(book.get('bids', []))} bids")
            all_ok &= check("Orderbook has asks", has_asks,
                           f"{len(book.get('asks', []))} asks")
            
            # Test midpoint
            mid = client.get_midpoint(test_token)
            all_ok &= check("Midpoint", mid is not None,
                           f"Midpoint: {mid}")
        else:
            all_ok &= check("Orderbook fetch", False, "No test market found")
    
    except Exception as e:
        all_ok &= check("Orderbook access", False, str(e))
    
    # ── 6. Balance Check ─────────────────────────────────────────
    print("\n6. Balance & Allowances")
    print("-" * 40)
    
    try:
        bal = client.get_balance_allowance()
        if isinstance(bal, dict):
            balance = bal.get("balance", "unknown")
            allowance = bal.get("allowance", "unknown")
            check("Balance data", True, f"Raw balance: {balance}, allowance: {allowance}")
            
            # Try to parse USDC balance (6 decimals)
            try:
                usdc = float(balance) / 1e6
                check("USDC balance", usdc > 0, f"${usdc:.2f} USDC")
                if usdc < 10:
                    print("     ⚠️  Low balance - deposit more USDC before trading")
            except:
                check("USDC parse", False, f"Could not parse: {balance}")
        else:
            check("Balance data", True, f"Response: {bal}")
    except Exception as e:
        check("Balance check", False, str(e))
        print("     ℹ️  Balance check may require allowances to be set first")
    
    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ ALL CHECKS PASSED - Ready for live trading!")
        print("\nNext steps:")
        print("  1. Add POLYMARKET_PROXY_ADDRESS to GitHub Secrets")
        print("  2. Add py-clob-client to requirements.txt")
        print("  3. Set LIVE_SHADOW_MODE=true for first test run")
        print("  4. When ready: set LIVE_TRADING_ENABLED=true")
    else:
        print("⚠️  SOME CHECKS FAILED - Review issues above")
        print("\nSetup guide:")
        print("  1. pip install py-clob-client web3==6.14.0")
        print("  2. Export your MetaMask private key")
        print("  3. Find your proxy address on polymarket.com → Deposit")
        print("  4. Set environment variables and re-run this script")
    print("=" * 60)
    
    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
