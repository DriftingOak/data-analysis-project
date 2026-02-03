#!/usr/bin/env python3
"""
POLYMARKET BOT - Backtest Module
=================================
Replay strategies on historical snapshots.

Usage:
    python backtest.py list                     # List available snapshots
    python backtest.py analyze <snapshot>       # Analyze a single snapshot
    python backtest.py compare <strat1> <strat2> # Compare strategies on all snapshots
    python backtest.py simulate <strategy>      # Full simulation on all snapshots

Examples:
    python backtest.py list
    python backtest.py analyze snapshots/snapshot_20260203_080000.json
    python backtest.py compare balanced aggressive
    python backtest.py simulate unlimited_wide
"""

import sys
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from snapshot import load_snapshot, list_snapshots, filter_snapshot_by_strategy, RunSnapshot
import strategies as strat_config


# =============================================================================
# BACKTEST STRUCTURES
# =============================================================================

@dataclass
class BacktestResult:
    """Result of a strategy backtest on a snapshot."""
    snapshot_id: str
    strategy_name: str
    timestamp: str
    
    # Markets
    total_eligible: int
    strategy_qualified: int
    
    # Price distribution
    avg_price_yes: float
    min_price_yes: float
    max_price_yes: float
    
    # Volume distribution
    avg_volume: float
    total_volume: float
    
    # Cluster breakdown
    by_cluster: Dict[str, int]


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def analyze_snapshot_for_strategy(
    snapshot: RunSnapshot,
    strategy_params: Dict,
) -> BacktestResult:
    """Analyze what a strategy would see in a snapshot."""
    
    # Filter markets by strategy params
    qualified = filter_snapshot_by_strategy(
        snapshot,
        price_yes_min=strategy_params.get("price_yes_min", 0),
        price_yes_max=strategy_params.get("price_yes_max", 1),
        min_volume=strategy_params.get("min_volume", 0),
        max_volume=strategy_params.get("max_volume", float("inf")),
    )
    
    # Apply cluster filter if present
    cluster_filter = strategy_params.get("cluster_filter")
    if cluster_filter:
        qualified = [m for m in qualified if m.cluster in cluster_filter]
    
    # Calculate stats
    if qualified:
        prices = [m.price_yes for m in qualified]
        volumes = [m.volume for m in qualified]
        avg_price = sum(prices) / len(prices)
        avg_volume = sum(volumes) / len(volumes)
    else:
        avg_price = 0
        avg_volume = 0
        prices = [0]
        volumes = [0]
    
    # Cluster breakdown
    by_cluster = {}
    for m in qualified:
        by_cluster[m.cluster] = by_cluster.get(m.cluster, 0) + 1
    
    return BacktestResult(
        snapshot_id=snapshot.run_id,
        strategy_name=strategy_params.get("name", "Unknown"),
        timestamp=snapshot.timestamp,
        total_eligible=len(snapshot.markets),
        strategy_qualified=len(qualified),
        avg_price_yes=avg_price,
        min_price_yes=min(prices) if prices else 0,
        max_price_yes=max(prices) if prices else 0,
        avg_volume=avg_volume,
        total_volume=sum(volumes),
        by_cluster=by_cluster,
    )


def compare_strategies_on_snapshot(
    snapshot: RunSnapshot,
    strategy_names: List[str],
) -> Dict[str, BacktestResult]:
    """Compare multiple strategies on a single snapshot."""
    results = {}
    
    for name in strategy_names:
        if name not in strat_config.STRATEGIES:
            print(f"[WARN] Unknown strategy: {name}")
            continue
        
        params = strat_config.STRATEGIES[name]
        results[name] = analyze_snapshot_for_strategy(snapshot, params)
    
    return results


def run_simulation(
    strategy_name: str,
    snapshots: List[str] = None,
) -> List[BacktestResult]:
    """Run a strategy simulation across all (or specified) snapshots."""
    
    if strategy_name not in strat_config.STRATEGIES:
        print(f"[ERROR] Unknown strategy: {strategy_name}")
        return []
    
    params = strat_config.STRATEGIES[strategy_name]
    
    if snapshots is None:
        snapshots = list_snapshots()
    
    results = []
    
    for snap_path in snapshots:
        snap = load_snapshot(snap_path)
        if snap:
            result = analyze_snapshot_for_strategy(snap, params)
            results.append(result)
    
    return results


# =============================================================================
# REPORTING
# =============================================================================

def print_snapshot_analysis(result: BacktestResult):
    """Print analysis of a single snapshot."""
    print(f"\n{'='*60}")
    print(f"Snapshot: {result.snapshot_id}")
    print(f"Strategy: {result.strategy_name}")
    print(f"Timestamp: {result.timestamp[:16]}")
    print(f"{'='*60}")
    
    print(f"\nMarkets:")
    print(f"  Total eligible (geo): {result.total_eligible}")
    print(f"  Strategy qualified:   {result.strategy_qualified}")
    
    print(f"\nPrice YES distribution:")
    print(f"  Min:  {result.min_price_yes:.1%}")
    print(f"  Avg:  {result.avg_price_yes:.1%}")
    print(f"  Max:  {result.max_price_yes:.1%}")
    
    print(f"\nVolume:")
    print(f"  Avg:   ${result.avg_volume:,.0f}")
    print(f"  Total: ${result.total_volume:,.0f}")
    
    if result.by_cluster:
        print(f"\nBy cluster:")
        for cluster, count in sorted(result.by_cluster.items(), key=lambda x: -x[1]):
            print(f"  {cluster}: {count}")


def print_strategy_comparison(
    snapshot: RunSnapshot,
    results: Dict[str, BacktestResult],
):
    """Print comparison of strategies on a snapshot."""
    print(f"\n{'='*70}")
    print(f"STRATEGY COMPARISON - {snapshot.run_id}")
    print(f"{'='*70}")
    
    # Header
    print(f"\n{'Strategy':<25} | {'Qualified':>10} | {'Avg YES':>8} | {'Avg Vol':>12}")
    print("-" * 70)
    
    for name, result in sorted(results.items(), key=lambda x: -x[1].strategy_qualified):
        print(
            f"{result.strategy_name:<25} | "
            f"{result.strategy_qualified:>10} | "
            f"{result.avg_price_yes:>7.1%} | "
            f"${result.avg_volume:>10,.0f}"
        )


def print_simulation_summary(results: List[BacktestResult], strategy_name: str):
    """Print summary of simulation across snapshots."""
    if not results:
        print("No results")
        return
    
    print(f"\n{'='*70}")
    print(f"SIMULATION SUMMARY: {strategy_name}")
    print(f"{'='*70}")
    print(f"Snapshots analyzed: {len(results)}")
    
    # Aggregate stats
    total_qualified = sum(r.strategy_qualified for r in results)
    avg_qualified = total_qualified / len(results)
    avg_price = sum(r.avg_price_yes for r in results) / len(results)
    
    print(f"\nAcross all snapshots:")
    print(f"  Avg markets per run: {avg_qualified:.1f}")
    print(f"  Total opportunities: {total_qualified}")
    print(f"  Avg YES price:       {avg_price:.1%}")
    
    # Trend over time
    print(f"\nTrend (first 5 → last 5 snapshots):")
    first_5 = results[:5] if len(results) >= 5 else results
    last_5 = results[-5:] if len(results) >= 5 else results
    
    avg_first = sum(r.strategy_qualified for r in first_5) / len(first_5)
    avg_last = sum(r.strategy_qualified for r in last_5) / len(last_5)
    
    print(f"  First 5 avg: {avg_first:.1f} markets")
    print(f"  Last 5 avg:  {avg_last:.1f} markets")
    
    # Cluster breakdown across all
    all_clusters = {}
    for r in results:
        for cluster, count in r.by_cluster.items():
            all_clusters[cluster] = all_clusters.get(cluster, 0) + count
    
    print(f"\nCluster distribution (total):")
    for cluster, count in sorted(all_clusters.items(), key=lambda x: -x[1]):
        print(f"  {cluster}: {count}")


# =============================================================================
# CLI
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        snapshots = list_snapshots()
        if not snapshots:
            print("No snapshots found. Run the bot to generate some.")
            return
        
        print(f"\nFound {len(snapshots)} snapshots:\n")
        for path in snapshots[-20:]:  # Last 20
            snap = load_snapshot(path)
            if snap:
                print(f"  {snap.run_id}: {snap.geo_markets_found:>4} markets | {snap.timestamp[:16]}")
        
        if len(snapshots) > 20:
            print(f"\n  ... and {len(snapshots) - 20} older snapshots")
    
    elif cmd == "analyze":
        if len(sys.argv) < 3:
            print("Usage: python backtest.py analyze <snapshot_file>")
            return
        
        snap = load_snapshot(sys.argv[2])
        if not snap:
            print(f"Could not load snapshot: {sys.argv[2]}")
            return
        
        # Analyze for all strategies
        print(f"\nAnalyzing {snap.run_id} for all strategies...\n")
        
        for strat_name in ["conservative", "balanced", "aggressive", "unlimited_wide"]:
            if strat_name in strat_config.STRATEGIES:
                result = analyze_snapshot_for_strategy(
                    snap, 
                    strat_config.STRATEGIES[strat_name]
                )
                print(f"{strat_name:<20}: {result.strategy_qualified:>4} markets | avg YES {result.avg_price_yes:.1%}")
    
    elif cmd == "compare":
        if len(sys.argv) < 4:
            print("Usage: python backtest.py compare <strategy1> <strategy2> [strategy3...]")
            return
        
        strategy_names = sys.argv[2:]
        snapshots = list_snapshots()
        
        if not snapshots:
            print("No snapshots found")
            return
        
        # Use most recent snapshot
        latest = load_snapshot(snapshots[-1])
        if not latest:
            print("Could not load latest snapshot")
            return
        
        results = compare_strategies_on_snapshot(latest, strategy_names)
        print_strategy_comparison(latest, results)
    
    elif cmd == "simulate":
        if len(sys.argv) < 3:
            print("Usage: python backtest.py simulate <strategy_name>")
            print(f"\nAvailable strategies: {list(strat_config.STRATEGIES.keys())}")
            return
        
        strategy_name = sys.argv[2]
        print(f"Running simulation for {strategy_name}...")
        
        results = run_simulation(strategy_name)
        print_simulation_summary(results, strategy_name)
    
    elif cmd == "strategies":
        strat_config.print_strategies()
    
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
