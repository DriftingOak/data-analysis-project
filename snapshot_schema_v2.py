"""
POLYMARKET BOT - Snapshot Schema V2
====================================
Data structures and I/O for market snapshots.

Designed for:
- Backtesting (replay decisions)
- Analysis (price buckets, volume filters)
- Future LLM classification

Standalone - no dependency on bot logic.
"""

import os
import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
from pathlib import Path


SCHEMA_VERSION = 2
SNAPSHOTS_DIR = "snapshots"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class MarketSnapshot:
    """
    Snapshot of a single market at time T.
    Contains everything needed to replay a trading decision.
    """
    # === IDENTIFIERS (stable) ===
    condition_id: str               # CANONICAL key - use for time series
    market_id: str = ""             # Polymarket app ID
    slug: str = ""                  # URL path (for debugging)
    
    # === TEXT (full, not truncated) ===
    question: str = ""
    description: str = ""
    resolution_source: str = ""
    
    # === PRICES ===
    price_yes: float = 0.5
    price_no: float = 0.5
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    spread_pct: Optional[float] = None
    last_trade_price: Optional[float] = None
    
    # === VOLUME & LIQUIDITY ===
    volume: float = 0.0
    volume_24h: Optional[float] = None
    liquidity: Optional[float] = None
    
    # === TOKEN IDs (for trading) ===
    token_id_yes: Optional[str] = None
    token_id_no: Optional[str] = None
    
    # === TIMESTAMPS ===
    created_ts: Optional[float] = None
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None
    closed_ts: Optional[float] = None
    
    # === LIFECYCLE FLAGS (raw from API) ===
    active: Optional[bool] = None
    closed: Optional[bool] = None
    archived: Optional[bool] = None
    restricted: Optional[bool] = None
    accepting_orders: Optional[bool] = None
    enable_order_book: Optional[bool] = None
    
    # === DERIVED ===
    tradable_now: bool = False
    days_to_close: Optional[float] = None
    
    # === CLASSIFICATION ===
    is_geopolitical: bool = False
    cluster: str = "other"
    capture_reason: str = ""
    
    # === POLYMARKET TAGS (if available) ===
    tag_ids: Optional[List[int]] = None


@dataclass
class RunMeta:
    """Metadata for a snapshot run."""
    schema_version: int = SCHEMA_VERSION
    run_id: str = ""
    run_ts: float = 0.0
    run_iso: str = ""
    
    # Traceability
    git_sha: str = ""
    filter_version: str = ""
    
    # Stats
    total_fetched: int = 0
    total_captured: int = 0
    total_geo: int = 0
    total_tradable: int = 0
    
    # Clusters breakdown
    clusters: Dict[str, int] = field(default_factory=dict)


# =============================================================================
# HELPERS
# =============================================================================

def parse_timestamp(value) -> Optional[float]:
    """Parse various timestamp formats to Unix timestamp."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return dt.timestamp()
        except:
            pass
        try:
            return float(value)
        except:
            pass
    return None


def safe_float(x, default=0.0) -> float:
    """Safe float conversion."""
    if x is None:
        return default
    try:
        return float(x)
    except:
        return default


def compute_tradable(market: Dict, current_ts: float) -> bool:
    """
    Is this market actually tradable right now?
    Conservative: ALL conditions must be met.
    """
    if not market.get("acceptingOrders", False):
        return False
    if not market.get("active", True):
        return False
    if market.get("closed", False):
        return False
    if market.get("archived", False):
        return False
    if market.get("restricted", False):
        return False
    
    # Check if not expired
    end_ts = parse_timestamp(market.get("endDate"))
    if end_ts and end_ts < current_ts:
        return False
    
    return True


def parse_prices(market: Dict) -> tuple[float, float]:
    """Parse YES and NO prices from market data."""
    try:
        prices_raw = market.get("outcomePrices", "")
        if isinstance(prices_raw, str) and prices_raw:
            prices = json.loads(prices_raw)
        elif isinstance(prices_raw, list):
            prices = prices_raw
        else:
            prices = []
        
        if len(prices) >= 1:
            price_yes = float(prices[0])
            price_no = 1 - price_yes
            return price_yes, price_no
    except:
        pass
    
    # Fallback to best ask/bid
    best_ask = safe_float(market.get("bestAsk"))
    if best_ask > 0:
        return best_ask, 1 - best_ask
    
    return 0.5, 0.5


def get_token_ids(market: Dict) -> Dict[str, Optional[str]]:
    """Extract YES and NO token IDs from market."""
    tokens = {"YES": None, "NO": None}
    
    clob_ids_raw = market.get("clobTokenIds", [])
    if isinstance(clob_ids_raw, str):
        try:
            clob_ids = json.loads(clob_ids_raw) if clob_ids_raw else []
        except:
            clob_ids = []
    else:
        clob_ids = clob_ids_raw or []
    
    outcomes_raw = market.get("outcomes", [])
    if isinstance(outcomes_raw, str):
        try:
            outcomes = json.loads(outcomes_raw) if outcomes_raw else []
        except:
            outcomes = []
    else:
        outcomes = outcomes_raw or []
    
    if clob_ids and outcomes:
        for i, outcome in enumerate(outcomes):
            if i < len(clob_ids) and isinstance(outcome, str):
                if outcome.lower() == "yes":
                    tokens["YES"] = str(clob_ids[i])
                elif outcome.lower() == "no":
                    tokens["NO"] = str(clob_ids[i])
    
    # Fallback: assume [YES, NO] order
    if not tokens["YES"] and not tokens["NO"] and len(clob_ids) == 2:
        tokens["YES"] = str(clob_ids[0])
        tokens["NO"] = str(clob_ids[1])
    
    return tokens


# =============================================================================
# BUILD SNAPSHOT
# =============================================================================

def build_market_snapshot(
    market: Dict[str, Any],
    run_ts: float,
    is_geopolitical: bool = False,
    cluster: str = "other",
    capture_reason: str = "",
) -> MarketSnapshot:
    """
    Build a MarketSnapshot from raw API data.
    """
    # IDs
    condition_id = str(market.get("conditionId", ""))
    market_id = str(market.get("id", ""))
    slug = market.get("slug", "") or ""
    
    # Text (FULL, not truncated)
    question = market.get("question", "") or ""
    description = market.get("description", "") or ""
    resolution_source = market.get("resolutionSource", "") or ""
    
    # Prices
    price_yes, price_no = parse_prices(market)
    best_bid = safe_float(market.get("bestBid"), None)
    best_ask = safe_float(market.get("bestAsk"), None)
    last_trade = safe_float(market.get("lastTradePrice"), None)
    
    # Spread
    spread = None
    spread_pct = None
    if best_bid is not None and best_ask is not None:
        spread = best_ask - best_bid
        if price_yes > 0:
            spread_pct = spread / price_yes
    
    # Volume
    volume = safe_float(market.get("volume"), 0.0)
    volume_24h = safe_float(market.get("volume24hr"), None)
    liquidity = safe_float(market.get("liquidity"), None)
    
    # Tokens
    tokens = get_token_ids(market)
    
    # Timestamps
    created_ts = parse_timestamp(market.get("createdAt"))
    start_ts = parse_timestamp(market.get("startDate"))
    end_ts = parse_timestamp(market.get("endDate"))
    closed_ts = parse_timestamp(market.get("closedTime"))
    
    # Days to close
    days_to_close = None
    if end_ts:
        days_to_close = (end_ts - run_ts) / (24 * 3600)
    
    # Tradable
    tradable_now = compute_tradable(market, run_ts)
    
    # Tags
    tag_ids = None
    if market.get("tags"):
        tag_ids = [
            t.get("id") for t in market.get("tags", [])
            if isinstance(t, dict) and t.get("id")
        ]
    
    return MarketSnapshot(
        condition_id=condition_id,
        market_id=market_id,
        slug=slug,
        
        question=question,
        description=description,
        resolution_source=resolution_source,
        
        price_yes=price_yes,
        price_no=price_no,
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        spread_pct=spread_pct,
        last_trade_price=last_trade,
        
        volume=volume,
        volume_24h=volume_24h,
        liquidity=liquidity,
        
        token_id_yes=tokens["YES"],
        token_id_no=tokens["NO"],
        
        created_ts=created_ts,
        start_ts=start_ts,
        end_ts=end_ts,
        closed_ts=closed_ts,
        
        active=market.get("active"),
        closed=market.get("closed"),
        archived=market.get("archived"),
        restricted=market.get("restricted"),
        accepting_orders=market.get("acceptingOrders"),
        enable_order_book=market.get("enableOrderBook"),
        
        tradable_now=tradable_now,
        days_to_close=days_to_close,
        
        is_geopolitical=is_geopolitical,
        cluster=cluster,
        capture_reason=capture_reason,
        
        tag_ids=tag_ids,
    )


# =============================================================================
# SAVE / LOAD
# =============================================================================

def save_snapshot(meta: RunMeta, markets: List[MarketSnapshot]) -> str:
    """
    Save a complete snapshot run to disk.
    Returns filepath.
    """
    Path(SNAPSHOTS_DIR).mkdir(exist_ok=True)
    
    run_id = meta.run_id
    filepath = Path(SNAPSHOTS_DIR) / f"snapshot_{run_id}.json"
    
    payload = {
        "meta": asdict(meta),
        "markets": [asdict(m) for m in markets],
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    
    print(f"[SNAPSHOT] Saved {len(markets)} markets to {filepath}")
    return str(filepath)


def load_snapshot(filepath: str) -> tuple[Optional[RunMeta], Optional[List[MarketSnapshot]]]:
    """Load a snapshot from disk."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        meta = RunMeta(**data["meta"])
        markets = [MarketSnapshot(**m) for m in data["markets"]]
        
        return meta, markets
    except Exception as e:
        print(f"[ERROR] Failed to load snapshot {filepath}: {e}")
        return None, None


def list_snapshots(directory: str = SNAPSHOTS_DIR) -> List[str]:
    """List all snapshot files, sorted chronologically."""
    if not os.path.exists(directory):
        return []
    
    files = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.startswith("snapshot_") and f.endswith(".json")
    ]
    return sorted(files)


# =============================================================================
# FILTERING HELPERS (for backtesting)
# =============================================================================

def filter_geo(markets: List[MarketSnapshot]) -> List[MarketSnapshot]:
    """Filter to geopolitical markets only."""
    return [m for m in markets if m.is_geopolitical]


def filter_tradable(markets: List[MarketSnapshot]) -> List[MarketSnapshot]:
    """Filter to tradable markets only."""
    return [m for m in markets if m.tradable_now]


def filter_price_range(
    markets: List[MarketSnapshot],
    price_min: float,
    price_max: float,
) -> List[MarketSnapshot]:
    """Filter by YES price range."""
    return [m for m in markets if price_min <= m.price_yes <= price_max]


def filter_volume(
    markets: List[MarketSnapshot],
    min_volume: float,
) -> List[MarketSnapshot]:
    """Filter by minimum volume."""
    return [m for m in markets if m.volume >= min_volume]


def filter_cluster(
    markets: List[MarketSnapshot],
    clusters: List[str],
) -> List[MarketSnapshot]:
    """Filter by cluster."""
    return [m for m in markets if m.cluster in clusters]
