"""
POLYMARKET BOT - Strategy
=========================
Trade selection logic based on simple rules.

UPDATED: Supports both old and new strategy key names:
- Old: bet_side, price_yes_min, price_yes_max
- New: side, price_min, price_max
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

import config

# =============================================================================
# IMPORTANT: Import depuis filters.py (nouveau filtre ENTITY + ACTION)
# =============================================================================
try:
    from filters import is_geopolitical, get_cluster
except ImportError:
    # Fallback if filters.py doesn't exist
    def is_geopolitical(question: str) -> bool:
        """Fallback geopolitical check using config keywords."""
        q = question.lower()
        geo_keywords = getattr(config, 'GEO_KEYWORDS', [])
        if geo_keywords:
            return any(kw.lower() in q for kw in geo_keywords)
        # Check GEO_REGIONS if available
        for region_data in getattr(config, 'GEO_REGIONS', {}).values():
            for values in region_data.values():
                if isinstance(values, list) and any(v.lower() in q for v in values):
                    return True
        return False
    
    def get_cluster(question: str) -> str:
        """Fallback cluster detection."""
        q = question.lower()
        for region_name, region_data in getattr(config, 'GEO_REGIONS', {}).items():
            for values in region_data.values():
                if isinstance(values, list) and any(v.lower() in q for v in values):
                    return region_name
        return "other"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TradeCandidate:
    market_id: str
    question: str
    token_id: str  # The token to buy (YES or NO token)
    bet_side: str  # "YES" or "NO"
    price_yes: float
    price_entry: float  # Price we pay (1 - price_yes for NO)
    volume: float
    cluster: str
    days_to_close: float
    end_ts: float


# =============================================================================
# HELPER: Get strategy param with fallback for old/new key names
# =============================================================================

def get_strategy_param(params: Dict, new_key: str, old_key: str, default):
    """Get a strategy parameter, supporting both old and new key names."""
    if params is None:
        return default
    # Try new key first, then old key, then default
    return params.get(new_key, params.get(old_key, default))


# =============================================================================
# FILTERING
# =============================================================================

def get_region_detail(question: str) -> str:
    """Get more detailed region for logging/analysis."""
    q = question.lower()
    
    for region_name, region_data in getattr(config, 'GEO_REGIONS', {}).items():
        for key, values in region_data.items():
            if isinstance(values, list):
                if any(v.lower() in q for v in values):
                    return region_name
    
    return "other"


def is_valid_market(
    market: Dict,
    timestamps: Dict[str, Optional[float]],
    current_ts: float,
    min_volume: float = None,
    max_volume: float = None,
) -> Tuple[bool, str]:
    """Check if market passes all filters.
    
    Returns:
        (is_valid, reason_if_invalid)
    """
    if min_volume is None:
        min_volume = getattr(config, 'MIN_VOLUME', 10000)
    if max_volume is None:
        max_volume = float("inf")
        
    question = market.get("question", "")
    
    # Must be geopolitical (uses ENTITY + ACTION from filters.py)
    if not is_geopolitical(question):
        return False, "not_geopolitical"
    
    # Check timestamps
    start_ts = timestamps.get("start_ts")
    end_ts = timestamps.get("end_ts")
    
    if start_ts is None or end_ts is None:
        return False, "missing_timestamps"
    
    # Buffer after open
    buffer_hours = getattr(config, 'BUFFER_HOURS', 48)
    hours_since_open = (current_ts - start_ts) / 3600
    if hours_since_open < buffer_hours:
        return False, "too_soon_after_open"
    
    # Buffer before close
    hours_until_end = (end_ts - current_ts) / 3600
    if hours_until_end < buffer_hours:
        return False, "too_close_to_end"
    
    # Volume filter
    volume = float(market.get("volume", 0) or 0)
    if volume < min_volume:
        return False, "low_volume"
    if volume > max_volume:
        return False, "high_volume"
    
    return True, "ok"


def is_valid_price(price_yes: float, price_min: float = None, price_max: float = None) -> bool:
    """Check if YES price is in target range."""
    if price_min is None:
        price_min = getattr(config, 'PRICE_YES_MIN', 0.02)
    if price_max is None:
        price_max = getattr(config, 'PRICE_YES_MAX', 0.60)
    return price_min <= price_yes <= price_max


# =============================================================================
# CANDIDATE SELECTION
# =============================================================================

def evaluate_market(
    market: Dict,
    timestamps: Dict[str, Optional[float]],
    tokens: Dict[str, str],
    current_ts: float,
    strategy_params: Dict = None,
) -> Optional[TradeCandidate]:
    """Evaluate a market and return TradeCandidate if it qualifies.
    
    Args:
        market: Market data from API
        timestamps: Parsed timestamps
        tokens: Token IDs for YES/NO
        current_ts: Current timestamp
        strategy_params: Optional dict with strategy overrides.
            Supports both old and new key names:
            - side / bet_side: "YES" or "NO"
            - price_min / price_yes_min: Minimum YES price
            - price_max / price_yes_max: Maximum YES price
            - min_volume: Minimum volume
            - max_volume: Maximum volume
    """
    # Use strategy params with fallback to old key names
    if strategy_params is None:
        strategy_params = {}
    
    # Support both old and new key names
    bet_side = get_strategy_param(strategy_params, "side", "bet_side", getattr(config, 'BET_SIDE', "NO"))
    price_yes_min = get_strategy_param(strategy_params, "price_min", "price_yes_min", getattr(config, 'PRICE_YES_MIN', 0.02))
    price_yes_max = get_strategy_param(strategy_params, "price_max", "price_yes_max", getattr(config, 'PRICE_YES_MAX', 0.60))
    min_volume = strategy_params.get("min_volume", getattr(config, 'MIN_VOLUME', 10000))
    max_volume = strategy_params.get("max_volume", float("inf"))
    
    # Basic validation
    is_valid, reason = is_valid_market(market, timestamps, current_ts, 
                                        min_volume=min_volume, max_volume=max_volume)
    if not is_valid:
        return None
    
    # Get YES price
    try:
        import json as json_module
        prices_raw = market.get("outcomePrices", "")
        if isinstance(prices_raw, str):
            prices = json_module.loads(prices_raw) if prices_raw else []
        else:
            prices = prices_raw or []
        
        outcomes_raw = market.get("outcomes", [])
        if isinstance(outcomes_raw, str):
            outcomes = json_module.loads(outcomes_raw) if outcomes_raw else []
        else:
            outcomes = outcomes_raw or []
        
        price_yes = None
        
        # First try to find explicit "Yes" outcome
        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, str) and outcome.lower() == "yes" and i < len(prices):
                price_yes = float(prices[i])
                break
        
        # If no "Yes" found and it's a binary market, use first price
        if price_yes is None and len(outcomes) == 2 and len(prices) >= 1:
            price_yes = float(prices[0])
        
        if price_yes is None:
            return None
            
    except Exception as e:
        return None
    
    # Check price range
    if not is_valid_price(price_yes, price_yes_min, price_yes_max):
        return None
    
    # Get token ID for our bet side
    if bet_side == "NO":
        token_id = tokens.get("NO")
        price_entry = 1 - price_yes  # NO price
    else:
        token_id = tokens.get("YES")
        price_entry = price_yes
    
    if not token_id:
        return None
    
    # Calculate days to close
    end_ts = timestamps.get("end_ts", 0)
    days_to_close = (end_ts - current_ts) / (24 * 3600)
    
    return TradeCandidate(
        market_id=market.get("id", ""),
        question=market.get("question", "")[:100],
        token_id=token_id,
        bet_side=bet_side,
        price_yes=price_yes,
        price_entry=price_entry,
        volume=float(market.get("volume", 0) or 0),
        cluster=get_cluster(market.get("question", "")),
        days_to_close=days_to_close,
        end_ts=end_ts,
    )


# =============================================================================
# PORTFOLIO MANAGEMENT
# =============================================================================

def calculate_exposure(positions: List[Dict]) -> Tuple[float, Dict[str, float]]:
    """Calculate current exposure from open positions.
    
    Returns:
        (total_exposure, exposure_by_cluster)
    """
    total = 0.0
    by_cluster = {}
    
    for pos in positions:
        size = float(pos.get("size", pos.get("size_usd", 0)))
        question = pos.get("question", "")
        cluster = get_cluster(question)
        
        total += size
        by_cluster[cluster] = by_cluster.get(cluster, 0) + size
    
    return total, by_cluster


def select_trades(
    candidates: List[TradeCandidate],
    cash_available: float,
    current_exposure: float,
    exposure_by_cluster: Dict[str, float],
    bankroll: float,
    existing_market_ids: set,
    max_exposure_pct: float = None,
    max_cluster_pct: float = None,
    bet_size: float = None,
) -> List[TradeCandidate]:
    """Select which trades to execute based on constraints.
    
    Returns list of TradeCandidate objects to execute.
    """
    if max_exposure_pct is None:
        max_exposure_pct = getattr(config, 'MAX_TOTAL_EXPOSURE_PCT', 0.60)
    if max_cluster_pct is None:
        max_cluster_pct = getattr(config, 'MAX_CLUSTER_EXPOSURE_PCT', 0.20)
    if bet_size is None:
        bet_size = getattr(config, 'BET_SIZE', 25.0)
    
    max_total = bankroll * max_exposure_pct
    max_cluster = bankroll * max_cluster_pct
    
    # Sort by volume (prefer more liquid markets)
    sorted_candidates = sorted(candidates, key=lambda x: x.volume, reverse=True)
    
    selected = []
    sim_exposure = current_exposure
    sim_cluster_exp = dict(exposure_by_cluster)
    
    for candidate in sorted_candidates:
        # Skip if already in this market
        if candidate.market_id in existing_market_ids:
            continue
        
        # Check if we have cash
        if cash_available < bet_size:
            break
        
        # Check total exposure
        if sim_exposure + bet_size > max_total:
            continue
        
        # Check cluster exposure
        cluster_exp = sim_cluster_exp.get(candidate.cluster, 0)
        if cluster_exp + bet_size > max_cluster:
            continue
        
        # Accept this trade
        selected.append(candidate)
        sim_exposure += bet_size
        sim_cluster_exp[candidate.cluster] = cluster_exp + bet_size
        cash_available -= bet_size
        existing_market_ids.add(candidate.market_id)
    
    return selected


# =============================================================================
# SUMMARY
# =============================================================================

def format_candidate_summary(candidate: TradeCandidate) -> str:
    """Format a candidate for logging."""
    return (
        f"{candidate.bet_side} @ {candidate.price_entry:.1%} | "
        f"YES={candidate.price_yes:.1%} | "
        f"Vol=${candidate.volume:,.0f} | "
        f"{candidate.days_to_close:.0f}d | "
        f"[{candidate.cluster}] | "
        f"{candidate.question[:50]}..."
    )
