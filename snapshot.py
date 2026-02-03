"""
POLYMARKET BOT - Snapshot Module
=================================
Records all eligible candidates at each run for backtesting.

Snapshots are stored in snapshots/ directory with timestamp.
Each snapshot contains:
- All markets that passed the geopolitical filter
- Current prices, volume, liquidity data
- Enough info to replay any strategy offline

Usage:
    from snapshot import save_snapshot, load_snapshot, list_snapshots
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

SNAPSHOTS_DIR = "snapshots"

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class MarketSnapshot:
    """Snapshot of a single market at a point in time."""
    market_id: str
    question: str
    
    # Prices
    price_yes: float
    price_no: float
    spread: Optional[float] = None
    
    # Volume & liquidity
    volume: float = 0.0
    volume_24h: Optional[float] = None
    liquidity: Optional[float] = None
    
    # Tokens
    token_id_yes: Optional[str] = None
    token_id_no: Optional[str] = None
    
    # Timestamps
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None
    days_to_close: Optional[float] = None
    
    # Classification
    cluster: str = "other"
    is_geopolitical: bool = True
    
    # Orderbook data (if available)
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    bid_depth: Optional[float] = None
    ask_depth: Optional[float] = None
    
    # Raw outcomes for multi-outcome markets
    outcomes: Optional[List[str]] = None
    outcome_prices: Optional[List[float]] = None


@dataclass 
class RunSnapshot:
    """Complete snapshot of a bot run."""
    timestamp: str
    run_id: str
    
    # All eligible markets (passed geo filter + basic validation)
    markets: List[MarketSnapshot]
    
    # Stats
    total_markets_scanned: int = 0
    geo_markets_found: int = 0
    
    # Metadata
    note: str = ""


# =============================================================================
# SNAPSHOT CREATION
# =============================================================================

def create_market_snapshot(
    market: Dict,
    timestamps: Dict,
    tokens: Dict,
    current_ts: float,
    cluster: str,
) -> MarketSnapshot:
    """Create a snapshot of a single market."""
    
    # Parse prices
    try:
        prices_raw = market.get("outcomePrices", "")
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw) if prices_raw else []
        else:
            prices = prices_raw or []
        
        outcomes_raw = market.get("outcomes", [])
        if isinstance(outcomes_raw, str):
            outcomes = json.loads(outcomes_raw) if outcomes_raw else []
        else:
            outcomes = outcomes_raw or []
        
        # Find YES price
        price_yes = None
        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, str) and outcome.lower() == "yes" and i < len(prices):
                price_yes = float(prices[i])
                break
        
        if price_yes is None and len(prices) >= 1:
            price_yes = float(prices[0])
        
        price_yes = price_yes or 0.5
        price_no = 1 - price_yes
        
    except Exception:
        price_yes = 0.5
        price_no = 0.5
        outcomes = []
        prices = []
    
    # Calculate days to close
    end_ts = timestamps.get("end_ts", 0)
    days_to_close = (end_ts - current_ts) / (24 * 3600) if end_ts else None
    
    # Get spread if available
    spread = market.get("spread")
    if spread is None and market.get("bestBid") and market.get("bestAsk"):
        try:
            spread = float(market.get("bestAsk", 0)) - float(market.get("bestBid", 0))
        except:
            pass
    
    return MarketSnapshot(
        market_id=str(market.get("id", market.get("conditionId", ""))),
        question=market.get("question", "")[:200],
        price_yes=price_yes,
        price_no=price_no,
        spread=spread,
        volume=float(market.get("volume", 0) or 0),
        volume_24h=float(market.get("volume24hr", 0) or 0) if market.get("volume24hr") else None,
        liquidity=float(market.get("liquidity", 0) or 0) if market.get("liquidity") else None,
        token_id_yes=tokens.get("YES"),
        token_id_no=tokens.get("NO"),
        start_ts=timestamps.get("start_ts"),
        end_ts=timestamps.get("end_ts"),
        days_to_close=days_to_close,
        cluster=cluster,
        is_geopolitical=True,
        best_bid=float(market.get("bestBid", 0)) if market.get("bestBid") else None,
        best_ask=float(market.get("bestAsk", 0)) if market.get("bestAsk") else None,
        outcomes=outcomes if len(outcomes) > 2 else None,
        outcome_prices=[float(p) for p in prices] if len(prices) > 2 else None,
    )


def save_snapshot(
    markets: List[MarketSnapshot],
    total_scanned: int = 0,
    note: str = "",
) -> str:
    """Save a snapshot to disk.
    
    Returns:
        Path to saved snapshot file
    """
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    
    now = datetime.now()
    run_id = now.strftime("%Y%m%d_%H%M%S")
    timestamp = now.isoformat()
    
    snapshot = RunSnapshot(
        timestamp=timestamp,
        run_id=run_id,
        markets=markets,
        total_markets_scanned=total_scanned,
        geo_markets_found=len(markets),
        note=note,
    )
    
    # Convert to dict (handle dataclasses)
    data = {
        "timestamp": snapshot.timestamp,
        "run_id": snapshot.run_id,
        "total_markets_scanned": snapshot.total_markets_scanned,
        "geo_markets_found": snapshot.geo_markets_found,
        "note": snapshot.note,
        "markets": [asdict(m) for m in snapshot.markets],
    }
    
    filepath = os.path.join(SNAPSHOTS_DIR, f"snapshot_{run_id}.json")
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"[SNAPSHOT] Saved {len(markets)} markets to {filepath}")
    return filepath


# =============================================================================
# SNAPSHOT LOADING
# =============================================================================

def load_snapshot(filepath: str) -> Optional[RunSnapshot]:
    """Load a snapshot from disk."""
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        
        markets = [MarketSnapshot(**m) for m in data.get("markets", [])]
        
        return RunSnapshot(
            timestamp=data["timestamp"],
            run_id=data["run_id"],
            markets=markets,
            total_markets_scanned=data.get("total_markets_scanned", 0),
            geo_markets_found=data.get("geo_markets_found", 0),
            note=data.get("note", ""),
        )
    except Exception as e:
        print(f"[ERROR] Failed to load snapshot {filepath}: {e}")
        return None


def list_snapshots() -> List[str]:
    """List all available snapshot files."""
    if not os.path.exists(SNAPSHOTS_DIR):
        return []
    
    files = [
        os.path.join(SNAPSHOTS_DIR, f) 
        for f in os.listdir(SNAPSHOTS_DIR) 
        if f.startswith("snapshot_") and f.endswith(".json")
    ]
    return sorted(files)


def get_latest_snapshot() -> Optional[str]:
    """Get path to most recent snapshot."""
    snapshots = list_snapshots()
    return snapshots[-1] if snapshots else None


# =============================================================================
# ANALYSIS HELPERS
# =============================================================================

def filter_snapshot_by_strategy(
    snapshot: RunSnapshot,
    price_yes_min: float,
    price_yes_max: float,
    min_volume: float = 0,
    max_volume: float = float("inf"),
    clusters: List[str] = None,
) -> List[MarketSnapshot]:
    """Filter a snapshot's markets by strategy parameters.
    
    Useful for backtesting: "what would strategy X have seen?"
    """
    filtered = []
    
    for market in snapshot.markets:
        # Price filter
        if not (price_yes_min <= market.price_yes <= price_yes_max):
            continue
        
        # Volume filter
        if not (min_volume <= market.volume <= max_volume):
            continue
        
        # Cluster filter
        if clusters and market.cluster not in clusters:
            continue
        
        filtered.append(market)
    
    return filtered


def compare_snapshots(snap1: RunSnapshot, snap2: RunSnapshot) -> Dict[str, Any]:
    """Compare two snapshots to see what changed.
    
    Returns dict with:
    - new_markets: Markets in snap2 but not snap1
    - closed_markets: Markets in snap1 but not snap2
    - price_changes: Markets with significant price movement
    """
    ids1 = {m.market_id for m in snap1.markets}
    ids2 = {m.market_id for m in snap2.markets}
    
    new_ids = ids2 - ids1
    closed_ids = ids1 - ids2
    common_ids = ids1 & ids2
    
    # Build lookup
    lookup1 = {m.market_id: m for m in snap1.markets}
    lookup2 = {m.market_id: m for m in snap2.markets}
    
    # Find significant price changes (>5%)
    price_changes = []
    for mid in common_ids:
        m1, m2 = lookup1[mid], lookup2[mid]
        delta = abs(m2.price_yes - m1.price_yes)
        if delta > 0.05:
            price_changes.append({
                "market_id": mid,
                "question": m2.question[:60],
                "price_old": m1.price_yes,
                "price_new": m2.price_yes,
                "delta": m2.price_yes - m1.price_yes,
            })
    
    return {
        "new_markets": [lookup2[mid] for mid in new_ids],
        "closed_markets": [lookup1[mid] for mid in closed_ids],
        "price_changes": sorted(price_changes, key=lambda x: abs(x["delta"]), reverse=True),
        "snap1_count": len(snap1.markets),
        "snap2_count": len(snap2.markets),
    }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python snapshot.py list              - List all snapshots")
        print("  python snapshot.py show <file>       - Show snapshot details")
        print("  python snapshot.py compare <f1> <f2> - Compare two snapshots")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        snapshots = list_snapshots()
        if not snapshots:
            print("No snapshots found")
        else:
            print(f"Found {len(snapshots)} snapshots:")
            for s in snapshots[-10:]:  # Last 10
                snap = load_snapshot(s)
                if snap:
                    print(f"  {snap.run_id}: {snap.geo_markets_found} markets @ {snap.timestamp[:16]}")
    
    elif cmd == "show" and len(sys.argv) > 2:
        snap = load_snapshot(sys.argv[2])
        if snap:
            print(f"Snapshot: {snap.run_id}")
            print(f"Timestamp: {snap.timestamp}")
            print(f"Markets scanned: {snap.total_markets_scanned}")
            print(f"Geo markets: {snap.geo_markets_found}")
            print(f"\nTop 10 by volume:")
            for m in sorted(snap.markets, key=lambda x: x.volume, reverse=True)[:10]:
                print(f"  YES={m.price_yes:.1%} Vol=${m.volume:,.0f} [{m.cluster}] {m.question[:50]}...")
    
    elif cmd == "compare" and len(sys.argv) > 3:
        s1 = load_snapshot(sys.argv[2])
        s2 = load_snapshot(sys.argv[3])
        if s1 and s2:
            diff = compare_snapshots(s1, s2)
            print(f"Comparing {s1.run_id} -> {s2.run_id}")
            print(f"New markets: {len(diff['new_markets'])}")
            print(f"Closed markets: {len(diff['closed_markets'])}")
            print(f"Price changes (>5%): {len(diff['price_changes'])}")
            if diff['price_changes'][:5]:
                print("\nBiggest moves:")
                for pc in diff['price_changes'][:5]:
                    print(f"  {pc['price_old']:.1%} -> {pc['price_new']:.1%} ({pc['delta']:+.1%}) {pc['question']}")
