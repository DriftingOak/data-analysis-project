"""
POLYMARKET BOT - Strategy
=========================
Trade selection logic based on simple rules.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

import config

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
# FILTERING
# =============================================================================

def is_geopolitical(question: str) -> bool:
    """Check if market is geopolitical based on keywords.
    
    Strategy:
    1. Must NOT contain any exclusion keyword
    2. Must contain at least one geo keyword OR one action keyword with geo context
    """
    q = question.lower()
    
    # First: hard exclusions (fast path out)
    if any(excl in q for excl in config.EXCLUDE_KEYWORDS):
        return False
    
    # Check for geo keywords
    has_geo = any(kw in q for kw in config.GEO_KEYWORDS)
    
    return has_geo


def get_cluster(question: str) -> str:
    """Identify which geopolitical cluster a market belongs to.
    
    Returns the FIRST matching cluster (order matters for priority).
    """
    q = question.lower()
    
    # Check clusters in priority order
    for cluster_name in ["ukraine", "mideast", "china", "latam", "europe", "africa"]:
        keywords = config.CLUSTERS.get(cluster_name, [])
        if any(kw in q for kw in keywords):
            return cluster_name
    
    return "other"


def get_region_detail(question: str) -> str:
    """Get more detailed region for logging/analysis."""
    q = question.lower()
    
    for region_name, region_data in config.GEO_REGIONS.items():
        for key, values in region_data.items():
            if isinstance(values, list):
                if any(v.lower() in q for v in values):
                    return region_name
    
    return "other"


def is_valid_market(
    market: Dict,
    timestamps: Dict[str, Optional[float]],
    current_ts: float
) -> Tuple[bool, str]:
    """Check if market passes all filters.
    
    Returns:
        (is_valid, reason_if_invalid)
    """
    question = market.get("question", "")
    
    # Must be geopolitical
    if not is_geopolitical(question):
        return False, "not_geopolitical"
    
    # Check timestamps
    start_ts = timestamps.get("start_ts")
    end_ts = timestamps.get("end_ts")
    
    if start_ts is None or end_ts is None:
        return False, "missing_timestamps"
    
    # Buffer after open
    hours_since_open = (current_ts - start_ts) / 3600
    if hours_since_open < config.BUFFER_HOURS:
        return False, "too_soon_after_open"
    
    # Buffer before close
    hours_until_end = (end_ts - current_ts) / 3600
    if hours_until_end < config.BUFFER_HOURS:
        return False, "too_close_to_end"
    
    # Volume filter
    volume = float(market.get("volume", 0) or 0)
    if volume < config.MIN_VOLUME:
        return False, "low_volume"
    
    return True, "ok"


def is_valid_price(price_yes: float) -> bool:
    """Check if YES price is in target range."""
    return config.PRICE_YES_MIN <= price_yes <= config.PRICE_YES_MAX


# =============================================================================
# CANDIDATE SELECTION
# =============================================================================

def evaluate_market(
    market: Dict,
    timestamps: Dict[str, Optional[float]],
    tokens: Dict[str, str],
    current_ts: float
) -> Optional[TradeCandidate]:
    """Evaluate a market and return TradeCandidate if it qualifies."""
    
    # Basic validation
    is_valid, reason = is_valid_market(market, timestamps, current_ts)
    if not is_valid:
        return None
    
    # Get YES price
    # outcomePrices is usually a JSON string like "[0.35, 0.65]"
    try:
        prices_raw = market.get("outcomePrices", "")
        if isinstance(prices_raw, str):
            import json
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw
        
        outcomes = market.get("outcomes", [])
        price_yes = None
        
        for i, outcome in enumerate(outcomes):
            if outcome.lower() == "yes" and i < len(prices):
                price_yes = float(prices[i])
                break
        
        if price_yes is None:
            return None
            
    except Exception as e:
        return None
    
    # Check price range
    if not is_valid_price(price_yes):
        return None
    
    # Get token ID for our bet side
    if config.BET_SIDE == "NO":
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
        bet_side=config.BET_SIDE,
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
        size = float(pos.get("size", 0))
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
    existing_market_ids: set
) -> List[TradeCandidate]:
    """Select which trades to execute based on constraints.
    
    Prioritization:
    - If cash is low (< 30%), prioritize fast-resolving markets
    - Otherwise, prioritize high volume (liquidity)
    """
    
    # Filter out markets we already have positions in
    candidates = [c for c in candidates if c.market_id not in existing_market_ids]
    
    if not candidates:
        return []
    
    # Determine prioritization mode
    cash_pct = cash_available / bankroll if bankroll > 0 else 0
    
    if cash_pct < config.MIN_CASH_PCT:
        # Low cash: prioritize fast resolution
        candidates.sort(key=lambda c: c.days_to_close)
        print(f"[INFO] Low cash mode ({cash_pct:.1%}): prioritizing fast resolution")
    else:
        # Normal: prioritize liquidity
        candidates.sort(key=lambda c: c.volume, reverse=True)
        print(f"[INFO] Normal mode ({cash_pct:.1%}): prioritizing volume")
    
    # Select trades within constraints
    selected = []
    running_exposure = current_exposure
    running_cluster_exposure = exposure_by_cluster.copy()
    
    max_total = bankroll * config.MAX_TOTAL_EXPOSURE_PCT
    max_cluster = bankroll * config.MAX_CLUSTER_EXPOSURE_PCT
    
    for candidate in candidates:
        # Check if we have enough cash
        if cash_available < config.BET_SIZE:
            print(f"[INFO] No more cash available (${cash_available:.2f})")
            break
        
        # Check total exposure
        if running_exposure + config.BET_SIZE > max_total:
            print(f"[INFO] Would exceed max total exposure ({running_exposure + config.BET_SIZE:.0f} > {max_total:.0f})")
            continue
        
        # Check cluster exposure
        cluster_exp = running_cluster_exposure.get(candidate.cluster, 0)
        if cluster_exp + config.BET_SIZE > max_cluster:
            print(f"[INFO] Would exceed max {candidate.cluster} exposure ({cluster_exp + config.BET_SIZE:.0f} > {max_cluster:.0f})")
            continue
        
        # Add to selection
        selected.append(candidate)
        cash_available -= config.BET_SIZE
        running_exposure += config.BET_SIZE
        running_cluster_exposure[candidate.cluster] = cluster_exp + config.BET_SIZE
    
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
