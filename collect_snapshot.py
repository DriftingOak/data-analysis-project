#!/usr/bin/env python3
"""
POLYMARKET BOT - Snapshot Collector
====================================
Standalone script to collect market snapshots.
Runs independently from the trading bot.

Usage:
    python collect_snapshot.py [--dry-run] [--limit N]

This script:
1. Fetches all open markets from Gamma API
2. Filters out obvious garbage (sports, crypto, entertainment)
3. Tags each market with geo classification
4. Saves snapshot JSON

Designed to run via GitHub Actions (.github/workflows/snapshot.yml)
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Local imports
from filters import classify_market, FILTER_VERSION
from snapshot_schema_v2 import (
    MarketSnapshot,
    RunMeta,
    build_market_snapshot,
    save_snapshot,
    SCHEMA_VERSION,
)


# =============================================================================
# CONFIG
# =============================================================================

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
DEFAULT_LIMIT = 8000
DEFAULT_PAGE_SIZE = 100


# =============================================================================
# API FUNCTIONS (standalone, no dependency on api.py)
# =============================================================================

def fetch_open_markets(limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    """
    Fetch open markets from Gamma API with pagination.
    
    Args:
        limit: Maximum total markets to fetch
    
    Returns:
        List of market dicts
    """
    all_markets = []
    offset = 0
    
    while len(all_markets) < limit:
        try:
            url = f"{GAMMA_API_BASE}/markets"
            params = {
                "closed": "false",
                "limit": min(DEFAULT_PAGE_SIZE, limit - len(all_markets)),
                "offset": offset,
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            markets = response.json()
            
            if not markets:
                break
            
            all_markets.extend(markets)
            offset += len(markets)
            
            # Progress
            if len(all_markets) % 500 == 0:
                log(f"Fetched {len(all_markets)} markets...")
            
            # API returned less than requested = no more data
            if len(markets) < DEFAULT_PAGE_SIZE:
                break
                
        except Exception as e:
            log(f"Error fetching markets at offset {offset}: {e}", "ERROR")
            break
    
    return all_markets[:limit]


# =============================================================================
# LOGGING
# =============================================================================

def log(msg: str, level: str = "INFO"):
    """Simple logging with timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


# =============================================================================
# MAIN COLLECTION LOGIC
# =============================================================================

def collect_snapshot(
    max_markets: int = DEFAULT_LIMIT,
    dry_run: bool = False,
) -> dict:
    """
    Collect a snapshot of all interesting markets.
    
    Args:
        max_markets: Maximum markets to fetch from API
        dry_run: If True, don't save file
    
    Returns:
        Stats dict
    """
    run_ts = datetime.now(timezone.utc).timestamp()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    git_sha = os.getenv("GITHUB_SHA", "local")[:12]
    
    log(f"Starting snapshot collection (run_id={run_id})")
    log(f"Filter version: {FILTER_VERSION}")
    
    # Fetch markets
    log(f"Fetching up to {max_markets} markets from Gamma API...")
    
    try:
        markets = fetch_open_markets(limit=max_markets)
    except Exception as e:
        log(f"Failed to fetch markets: {e}", "ERROR")
        return {"error": str(e)}
    
    log(f"Fetched {len(markets)} markets from API")
    
    # Process markets
    captured: List[MarketSnapshot] = []
    stats = {
        "fetched": len(markets),
        "captured": 0,
        "garbage": 0,
        "geo": 0,
        "tradable": 0,
        "clusters": {},
    }
    
    for market in markets:
        question = market.get("question", "") or ""
        
        # Classify
        classification = classify_market(question)
        
        # Skip garbage
        if not classification.should_capture:
            stats["garbage"] += 1
            continue
        
        # Build snapshot
        snap = build_market_snapshot(
            market=market,
            run_ts=run_ts,
            is_geopolitical=classification.is_geopolitical,
            cluster=classification.cluster,
            capture_reason=classification.capture_reason,
        )
        
        captured.append(snap)
        stats["captured"] += 1
        
        if classification.is_geopolitical:
            stats["geo"] += 1
            cluster = classification.cluster
            stats["clusters"][cluster] = stats["clusters"].get(cluster, 0) + 1
        
        if snap.tradable_now:
            stats["tradable"] += 1
    
    # Log summary
    log(f"Capture complete:")
    log(f"  - Fetched:  {stats['fetched']}")
    log(f"  - Captured: {stats['captured']}")
    log(f"  - Garbage:  {stats['garbage']}")
    log(f"  - Geo:      {stats['geo']}")
    log(f"  - Tradable: {stats['tradable']}")
    log(f"  - Clusters: {stats['clusters']}")
    
    # Build run meta
    meta = RunMeta(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        run_ts=run_ts,
        run_iso=datetime.fromtimestamp(run_ts, tz=timezone.utc).isoformat(),
        git_sha=git_sha,
        filter_version=FILTER_VERSION,
        total_fetched=stats["fetched"],
        total_captured=stats["captured"],
        total_geo=stats["geo"],
        total_tradable=stats["tradable"],
        clusters=stats["clusters"],
    )
    
    # Save
    if not dry_run:
        filepath = save_snapshot(meta, captured)
        stats["filepath"] = filepath
        log(f"Saved to {filepath}")
    else:
        log("Dry run - not saving")
    
    return stats


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Collect Polymarket snapshot for backtesting"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Don't save file, just show stats"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=DEFAULT_LIMIT, 
        help="Max markets to fetch"
    )
    args = parser.parse_args()
    
    stats = collect_snapshot(
        max_markets=args.limit,
        dry_run=args.dry_run,
    )
    
    if "error" in stats:
        log(f"Collection failed: {stats['error']}", "ERROR")
        sys.exit(1)
    
    # Final summary
    print("\n" + "=" * 50)
    print("SNAPSHOT SUMMARY")
    print("=" * 50)
    print(f"Fetched:         {stats.get('fetched', 0):,}")
    print(f"Captured:        {stats.get('captured', 0):,}")
    print(f"Garbage:         {stats.get('garbage', 0):,}")
    print(f"Geopolitical:    {stats.get('geo', 0):,}")
    print(f"Tradable now:    {stats.get('tradable', 0):,}")
    
    if stats.get("clusters"):
        print("\nBy cluster:")
        for cluster, count in sorted(stats["clusters"].items(), key=lambda x: -x[1]):
            print(f"  {cluster}: {count}")
    
    if stats.get("filepath"):
        print(f"\nSaved to: {stats['filepath']}")


if __name__ == "__main__":
    main()
