"""
POLYMARKET BOT - Strategy Definitions
=====================================
24 strategies organized in tiers for systematic paper trading validation.

STRATEGY GROUPS:
- Base (4): Original strategies, kept for continuity
- Tier 1 - Controls (4): Baselines to validate the signal exists live
- Tier 2 - Volume Hypothesis (3): Validate volume as predictor #1
- Tier 3 - Multi-Bucket (4): Conditional zones by volume
- Tier 4 - Cash-Constrained (5): Deadline filter impact
- Tier 5 - Deployable (4): Final candidates for real trading

NEW CONFIG KEYS (not yet handled by bot.py — Phase 2):
- zones: list of {vol_min, vol_max, price_yes_min, price_yes_max} for multi-bucket
- sizing: "fixed" or "adaptive" (adaptive uses volume-based bet sizing)
- priority: "price_high" | "volume_low" | "rotation" (composite)
- deadline_min / deadline_max: filter by days to resolution
- event_cap: max positions per event_id (not market_id)
- exclude_series: skip markets with structure=series
"""

from typing import Any, Dict, List

# =============================================================================
# ADAPTIVE SIZING HELPER (for reference — actual logic goes in bot.py)
# =============================================================================
# if volume < 5_000:    bet = 5
# elif volume < 50_000: bet = 10
# else:                 bet = 25

# =============================================================================
# COMMON DEFAULTS
# =============================================================================
_DEFAULTS = {
    "bet_side": "NO",
    "entry_cost_rate": 0.005,       # 0.5% spread for limit orders
    "max_total_exposure_pct": 0.90,  # High for paper trading (max data)
    "max_cluster_exposure_pct": 0.30,  # 30% per region (doc rule)
}


def _strat(name, description, bankroll, zone_or_zones, **overrides):
    """Helper to build a strategy dict with sensible defaults."""
    s = dict(_DEFAULTS)
    s["name"] = name
    s["description"] = description
    s["bankroll"] = bankroll
    s["portfolio_file"] = f"portfolio_{name}.json"

    # Zone: simple (min/max) or multi-bucket (list of dicts)
    if isinstance(zone_or_zones, tuple):
        s["price_yes_min"] = zone_or_zones[0]
        s["price_yes_max"] = zone_or_zones[1]
    elif isinstance(zone_or_zones, list):
        s["zones"] = zone_or_zones
        # Set outer bounds for backwards compat / simple filtering
        all_mins = [z["price_yes_min"] for z in zone_or_zones if z.get("price_yes_min") is not None]
        all_maxs = [z["price_yes_max"] for z in zone_or_zones if z.get("price_yes_max") is not None]
        s["price_yes_min"] = min(all_mins) if all_mins else 0.0
        s["price_yes_max"] = max(all_maxs) if all_maxs else 1.0

    # Apply overrides
    s.update(overrides)

    # Defaults for new keys if not set
    s.setdefault("min_volume", 0)
    s.setdefault("max_volume", float("inf"))
    s.setdefault("sizing", "fixed")
    s.setdefault("bet_size", 25.0)
    s.setdefault("priority", "price_high")
    s.setdefault("deadline_min", 3)
    s.setdefault("deadline_max", None)
    s.setdefault("event_cap", 3)
    s.setdefault("exclude_series", False)

    return s


# =============================================================================
# STRATEGIES
# =============================================================================

STRATEGIES: Dict[str, Dict[str, Any]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# BASE — Original 4 strategies (kept for portfolio continuity)
# ─────────────────────────────────────────────────────────────────────────────

STRATEGIES["conservative"] = {
    "name": "Conservative",
    "description": "High win rate, low risk - targets very likely NO outcomes",
    "bet_side": "NO",
    "price_yes_min": 0.10,
    "price_yes_max": 0.25,
    "min_volume": 10000,
    "max_volume": float("inf"),
    "max_total_exposure_pct": 0.60,
    "max_cluster_exposure_pct": 0.20,
    "bet_size": 25.0,
    "bankroll": 5000.0,
    "entry_cost_rate": 0.03,
    "portfolio_file": "portfolio_conservative.json",
    # Legacy keys for compat
    "sizing": "fixed",
    "priority": "price_high",
    "deadline_min": 3,
    "deadline_max": None,
    "event_cap": 3,
    "exclude_series": False,
}

STRATEGIES["balanced"] = {
    "name": "Balanced",
    "description": "Balanced risk/reward - the baseline strategy from backtest",
    "bet_side": "NO",
    "price_yes_min": 0.20,
    "price_yes_max": 0.60,
    "min_volume": 10000,
    "max_volume": float("inf"),
    "max_total_exposure_pct": 0.60,
    "max_cluster_exposure_pct": 0.20,
    "bet_size": 25.0,
    "bankroll": 5000.0,
    "entry_cost_rate": 0.03,
    "portfolio_file": "portfolio_balanced.json",
    "sizing": "fixed",
    "priority": "price_high",
    "deadline_min": 3,
    "deadline_max": None,
    "event_cap": 3,
    "exclude_series": False,
}

STRATEGIES["aggressive"] = {
    "name": "Aggressive",
    "description": "Higher risk, targets the 30-60% sweet spot",
    "bet_side": "NO",
    "price_yes_min": 0.30,
    "price_yes_max": 0.60,
    "min_volume": 10000,
    "max_volume": float("inf"),
    "max_total_exposure_pct": 0.75,
    "max_cluster_exposure_pct": 0.25,
    "bet_size": 30.0,
    "bankroll": 5000.0,
    "entry_cost_rate": 0.03,
    "portfolio_file": "portfolio_aggressive.json",
    "sizing": "fixed",
    "priority": "price_high",
    "deadline_min": 3,
    "deadline_max": None,
    "event_cap": 3,
    "exclude_series": False,
}

STRATEGIES["volume_sweet"] = {
    "name": "Volume Sweet Spot",
    "description": "Targets the 15k-100k volume range where edge was strongest",
    "bet_side": "NO",
    "price_yes_min": 0.20,
    "price_yes_max": 0.60,
    "min_volume": 15000,
    "max_volume": 100000,
    "max_total_exposure_pct": 0.60,
    "max_cluster_exposure_pct": 0.20,
    "bet_size": 25.0,
    "bankroll": 5000.0,
    "entry_cost_rate": 0.03,
    "portfolio_file": "portfolio_volume_sweet.json",
    "sizing": "fixed",
    "priority": "price_high",
    "deadline_min": 3,
    "deadline_max": None,
    "event_cap": 3,
    "exclude_series": False,
}


# ─────────────────────────────────────────────────────────────────────────────
# TIER 1 — Controls (4 bots)
# Objective: establish baselines, validate signal exists live
# ─────────────────────────────────────────────────────────────────────────────

STRATEGIES["t1_baseline_flat"] = _strat(
    name="t1_baseline_flat",
    description="Control: does the NO signal exist live? Flat 40-80% zone",
    bankroll=1000,
    zone_or_zones=(0.40, 0.80),
    bet_size=25, sizing="fixed", priority="price_high",
)

STRATEGIES["t1_baseline_v1_zone"] = _strat(
    name="t1_baseline_v1_zone",
    description="Control: old 20-60% zone vs new 40-80%? Expected: underperform",
    bankroll=1000,
    zone_or_zones=(0.20, 0.60),
    bet_size=25, sizing="fixed", priority="price_high",
)

STRATEGIES["t1_baseline_volume_high"] = _strat(
    name="t1_baseline_volume_high",
    description="Negative control: high-volume markets have edge? Expected: ~0% ROI",
    bankroll=1000,
    zone_or_zones=(0.50, 0.80),
    min_volume=250000,
    bet_size=25, sizing="fixed", priority="price_high",
)

STRATEGIES["t1_baseline_contrarian"] = _strat(
    name="t1_baseline_contrarian",
    description="Control: ultra-safe low prices. Expected: high WR, low ROI",
    bankroll=1000,
    zone_or_zones=(0.10, 0.35),
    bet_size=25, sizing="fixed", priority="price_high",
)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 2 — Volume Hypothesis (3 bots)
# Objective: validate volume as predictor #1
# ─────────────────────────────────────────────────────────────────────────────

STRATEGIES["t2_small_vol"] = _strat(
    name="t2_small_vol",
    description="Core strategy: volume <100k captures the edge. Backtest: +181% ROI",
    bankroll=1000,
    zone_or_zones=(0.40, 0.80),
    max_volume=100000,
    sizing="adaptive", priority="volume_low",
)

STRATEGIES["t2_micro_vol"] = _strat(
    name="t2_micro_vol",
    description="Micro markets (<50k) goldmine? Shifted zone. Backtest: +153% ROI",
    bankroll=1000,
    zone_or_zones=(0.30, 0.65),
    max_volume=50000,
    sizing="adaptive", priority="volume_low",
)

STRATEGIES["t2_noseries"] = _strat(
    name="t2_noseries",
    description="Exclude series structure. Backtest: +27.6% ROI, best ROI/DD",
    bankroll=1000,
    zone_or_zones=(0.40, 0.80),
    sizing="adaptive", priority="volume_low",
    exclude_series=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3 — Multi-Bucket (4 bots)
# Objective: validate conditional zones by volume
# ─────────────────────────────────────────────────────────────────────────────

STRATEGIES["t3_mb_simple"] = _strat(
    name="t3_mb_simple",
    description="2-bucket: different zones by volume. If beats t2_small_vol, concept validated",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 100000,       "price_yes_min": 0.30, "price_yes_max": 0.65},
        {"vol_min": 100000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    sizing="adaptive", priority="volume_low",
)

STRATEGIES["t3_mb_3bucket"] = _strat(
    name="t3_mb_3bucket",
    description="3-bucket: granularity sweet spot. Backtest: +73.9% ROI, 13.7% DD",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 25000,        "price_yes_min": 0.30, "price_yes_max": 0.60},
        {"vol_min": 25000,   "vol_max": 250000,       "price_yes_min": 0.40, "price_yes_max": 0.70},
        {"vol_min": 250000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    sizing="adaptive", priority="volume_low",
)

STRATEGIES["t3_mb_4bucket_skip"] = _strat(
    name="t3_mb_4bucket_skip",
    description="4-bucket with dead zone skip (100k-250k). Backtest: +99% ROI, best ROI/DD",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 25000,        "price_yes_min": 0.30, "price_yes_max": 0.60},
        {"vol_min": 25000,   "vol_max": 100000,       "price_yes_min": 0.40, "price_yes_max": 0.70},
        # 100k-250k: SKIP (dead zone)
        {"vol_min": 250000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    # Markets with volume 100k-250k will be excluded because no bucket matches
    sizing="adaptive", priority="volume_low",
)

STRATEGIES["t3_mb_aggressive"] = _strat(
    name="t3_mb_aggressive",
    description="4-bucket aggressive zones. Max overfit risk. Tests if fine zones add value",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 5000,         "price_yes_min": 0.30, "price_yes_max": 0.65},
        {"vol_min": 5000,    "vol_max": 50000,        "price_yes_min": 0.35, "price_yes_max": 0.70},
        {"vol_min": 50000,   "vol_max": 250000,       "price_yes_min": 0.40, "price_yes_max": 0.80},
        {"vol_min": 250000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    sizing="adaptive", priority="volume_low",
)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 4 — Cash-Constrained + Deadline (5 bots)
# Objective: validate deadline filter as performance transformer
# ─────────────────────────────────────────────────────────────────────────────

STRATEGIES["t4_cstr_baseline"] = _strat(
    name="t4_cstr_baseline",
    description="Cash-constrained baseline, no deadline. MUST FAIL (-93%). Validates hypothesis",
    bankroll=500,
    zone_or_zones=(0.40, 0.80),
    bet_size=50, sizing="fixed", priority="volume_low",
)

STRATEGIES["t4_cstr_dl60"] = _strat(
    name="t4_cstr_dl60",
    description="Same as cstr_baseline + deadline 3-60d. Backtest: +131.6%. THE key test",
    bankroll=500,
    zone_or_zones=(0.40, 0.80),
    bet_size=50, sizing="fixed", priority="volume_low",
    deadline_max=60,
)

STRATEGIES["t4_cstr_rotation_dl60"] = _strat(
    name="t4_cstr_rotation_dl60",
    description="Rotation priority in constrained. Backtest: +209.8% (best ROI overall)",
    bankroll=500,
    zone_or_zones=(0.40, 0.80),
    bet_size=50, sizing="fixed", priority="rotation",
    deadline_max=60,
)

STRATEGIES["t4_cstr_adaptive_dl90"] = _strat(
    name="t4_cstr_adaptive_dl90",
    description="Adaptive sizing for more diversification in constrained. Backtest: +101%",
    bankroll=1000,
    zone_or_zones=(0.40, 0.80),
    sizing="adaptive", priority="volume_low",
    deadline_max=90,
)

STRATEGIES["t4_cstr_mb3_dl90"] = _strat(
    name="t4_cstr_mb3_dl90",
    description="MB3 + deadline combo in constrained. Best of both worlds. Backtest: +110.6%",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 25000,        "price_yes_min": 0.30, "price_yes_max": 0.60},
        {"vol_min": 25000,   "vol_max": 250000,       "price_yes_min": 0.40, "price_yes_max": 0.70},
        {"vol_min": 250000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    sizing="adaptive", priority="volume_low",
    deadline_max=90,
)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 5 — Deployable Configs (4 bots)
# Objective: final candidates for real trading
# ─────────────────────────────────────────────────────────────────────────────

STRATEGIES["t5_deploy_conservative"] = _strat(
    name="t5_deploy_conservative",
    description="Min risk, max ROI/DD (8.7x). Micro focus, skip >250k. Backtest: +31.4%, DD 3.6%",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 50000,        "price_yes_min": 0.30, "price_yes_max": 0.65},
        {"vol_min": 50000,   "vol_max": 250000,       "price_yes_min": 0.40, "price_yes_max": 0.75},
        # >250k: SKIP
    ],
    sizing="adaptive", priority="volume_low",
    event_cap=2,
)

STRATEGIES["t5_deploy_balanced"] = _strat(
    name="t5_deploy_balanced",
    description="Good ROI with controlled DD. Backtest: +39%, DD 8.3%, 13.6 turns/yr",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 25000,        "price_yes_min": 0.30, "price_yes_max": 0.60},
        {"vol_min": 25000,   "vol_max": 250000,       "price_yes_min": 0.40, "price_yes_max": 0.70},
        {"vol_min": 250000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    sizing="adaptive", priority="rotation",
    deadline_max=90,
)

STRATEGIES["t5_deploy_speed"] = _strat(
    name="t5_deploy_speed",
    description="Max rotation for min capital. 19 turns/yr. Backtest: +16.5%, DD 4.1%",
    bankroll=500,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 50000,        "price_yes_min": 0.30, "price_yes_max": 0.65},
        {"vol_min": 50000,   "vol_max": 250000,       "price_yes_min": 0.40, "price_yes_max": 0.75},
        # >250k: SKIP
    ],
    sizing="adaptive", priority="rotation",
    deadline_max=60,
)

STRATEGIES["t5_deploy_max_growth"] = _strat(
    name="t5_deploy_max_growth",
    description="Max ROI, high DD accepted. Backtest: +110.6%, DD 41.3%. Aggressive but realistic",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 25000,        "price_yes_min": 0.30, "price_yes_max": 0.60},
        {"vol_min": 25000,   "vol_max": 250000,       "price_yes_min": 0.40, "price_yes_max": 0.70},
        {"vol_min": 250000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    bet_size=50, sizing="fixed", priority="volume_low",
    deadline_max=90,
)


# =============================================================================
# STRATEGY GROUPS
# =============================================================================

STRATEGY_GROUPS: Dict[str, List[str]] = {
    # Original base
    "base": ["conservative", "balanced", "aggressive", "volume_sweet"],

    # New tiers
    "tier1": [k for k in STRATEGIES if k.startswith("t1_")],
    "tier2": [k for k in STRATEGIES if k.startswith("t2_")],
    "tier3": [k for k in STRATEGIES if k.startswith("t3_")],
    "tier4": [k for k in STRATEGIES if k.startswith("t4_")],
    "tier5": [k for k in STRATEGIES if k.startswith("t5_")],

    # Convenience
    "controls": [k for k in STRATEGIES if k.startswith("t1_")],
    "deployable": [k for k in STRATEGIES if k.startswith("t5_")],

    # Combo groups
    "standard": ["conservative", "balanced", "aggressive", "volume_sweet"],
    "new": [k for k in STRATEGIES if k.startswith("t")],
    "all": list(STRATEGIES.keys()),

    # Phased rollout
    "phase1": [
        "conservative", "balanced", "aggressive", "volume_sweet",
        "t1_baseline_flat", "t1_baseline_v1_zone", "t1_baseline_volume_high", "t1_baseline_contrarian",
        "t2_small_vol", "t2_micro_vol",
    ],
    "phase2": [k for k in STRATEGIES if k.startswith("t3_")] + ["t2_noseries"],
    "phase3": [k for k in STRATEGIES if k.startswith("t4_")],
    "phase4": [k for k in STRATEGIES if k.startswith("t5_")],

    # Quick test
    "quick": ["balanced", "t1_baseline_flat"],
}


# =============================================================================
# HELPERS
# =============================================================================

def get_strategy(name: str) -> dict:
    """Get strategy config by name."""
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGIES.keys())}")
    return STRATEGIES[name]


def get_strategy_group(group_name: str) -> list:
    """Get list of strategy names in a group."""
    if group_name not in STRATEGY_GROUPS:
        raise ValueError(f"Unknown group: {group_name}. Available: {list(STRATEGY_GROUPS.keys())}")
    return STRATEGY_GROUPS[group_name]


def get_zone_for_volume(strategy: dict, volume: float):
    """Get the price zone for a given volume, using multi-bucket if available.
    
    Returns (price_yes_min, price_yes_max) or None if volume falls in a skip zone.
    """
    zones = strategy.get("zones")
    if not zones:
        # Simple zone
        return (strategy["price_yes_min"], strategy["price_yes_max"])

    # Multi-bucket: find matching zone
    for z in zones:
        vol_min = z.get("vol_min", 0)
        vol_max = z.get("vol_max", float("inf"))
        if vol_min <= volume < vol_max:
            return (z["price_yes_min"], z["price_yes_max"])

    # No matching bucket = skip zone (dead zone)
    return None


def get_bet_size(strategy: dict, volume: float) -> float:
    """Get bet size based on strategy sizing mode and market volume."""
    if strategy.get("sizing") == "adaptive":
        if volume < 5000:
            return 5.0
        elif volume < 50000:
            return 10.0
        else:
            return 25.0
    return strategy.get("bet_size", 25.0)


def compute_rotation_score(candidate, all_candidates) -> float:
    """Compute composite rotation score.
    
    rotation = rank(volume_low) + rank(deadline_short) + rank(price_high)
    Lower score = better candidate.
    """
    # This is a placeholder — actual ranking needs the full candidate list
    # and will be implemented in bot.py Phase 2
    score = 0.0

    # Volume: lower is better
    if hasattr(candidate, 'volume') and candidate.volume > 0:
        score += candidate.volume / 1000  # rough proxy

    # Deadline: shorter is better
    if hasattr(candidate, 'days_to_close') and candidate.days_to_close > 0:
        score += candidate.days_to_close

    # Price: higher YES is better (for NO bets)
    if hasattr(candidate, 'price_yes'):
        score -= candidate.price_yes * 100  # bonus for high price

    return score


def list_strategies() -> list:
    """List all available strategy names."""
    return list(STRATEGIES.keys())


def list_groups() -> list:
    """List all strategy group names."""
    return list(STRATEGY_GROUPS.keys())


def print_strategies():
    """Print all strategies with descriptions."""
    print("\n" + "=" * 80)
    print("AVAILABLE STRATEGIES (24 total)")
    print("=" * 80)

    groups = [
        ("Base (original)", [k for k in STRATEGIES if not k.startswith("t")]),
        ("Tier 1 — Controls", [k for k in STRATEGIES if k.startswith("t1_")]),
        ("Tier 2 — Volume Hypothesis", [k for k in STRATEGIES if k.startswith("t2_")]),
        ("Tier 3 — Multi-Bucket", [k for k in STRATEGIES if k.startswith("t3_")]),
        ("Tier 4 — Cash-Constrained", [k for k in STRATEGIES if k.startswith("t4_")]),
        ("Tier 5 — Deployable", [k for k in STRATEGIES if k.startswith("t5_")]),
    ]

    for group_name, strat_names in groups:
        print(f"\n{group_name}:")
        print("-" * 70)
        for name in strat_names:
            s = STRATEGIES[name]
            sizing = s.get("sizing", "fixed")
            prio = s.get("priority", "price_high")
            dl = s.get("deadline_max")
            dl_str = f"dl≤{dl}d" if dl else "no dl"
            zones = s.get("zones")
            if zones:
                zone_str = f"{len(zones)}-bucket"
            else:
                pmin = s.get("price_yes_min", 0) * 100
                pmax = s.get("price_yes_max", 1) * 100
                zone_str = f"{pmin:.0f}-{pmax:.0f}%"
            br = s.get("bankroll", 1000)
            print(f"  {name:30} | ${br:.0f} | {zone_str:12} | {sizing:8} | {prio:10} | {dl_str}")

    print("\n" + "=" * 80)
    print("STRATEGY GROUPS")
    print("=" * 80)
    for group, members in STRATEGY_GROUPS.items():
        count = len(members)
        preview = ", ".join(members[:3])
        suffix = f"... (+{count - 3})" if count > 3 else ""
        print(f"  {group:15} ({count:2}) -> {preview}{suffix}")


if __name__ == "__main__":
    print_strategies()
