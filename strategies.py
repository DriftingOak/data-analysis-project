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
        "mode": "paper",  # "paper" or "live"
    "description": "Mise NO sur les marchés à 10-25% YES (très peu probable). Petits gains fréquents. Volume min 10k$.",
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
        "mode": "paper",  # "paper" or "live"
    "description": "Mise NO sur les marchés à 20-60% YES. Zone large, stratégie de référence. Volume min 10k$.",
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
        "mode": "paper",  # "paper" or "live"
    "description": "Mise NO sur les marchés à 30-60% YES. Zone plus risquée mais meilleur rendement par trade. Volume min 10k$.",
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
        "mode": "paper",  # "paper" or "live"
    "description": "Mise NO sur marchés à 20-60% YES, volume limité à 15k-100k$. Cible les marchés moyens où l'edge est le plus fort.",
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
    description="Contrôle : mise NO zone 40-80% YES, $25 fixe. Vérifie que le signal de salience existe en live.",
    bankroll=1000,
    zone_or_zones=(0.40, 0.80),
    bet_size=25, sizing="fixed", priority="price_high",
)

STRATEGIES["t1_baseline_v1_zone"] = _strat(
    name="t1_baseline_v1_zone",
    description="Contrôle : ancienne zone 20-60% YES. Compare à la nouvelle zone 40-80%. Devrait sous-performer.",
    bankroll=1000,
    zone_or_zones=(0.20, 0.60),
    bet_size=25, sizing="fixed", priority="price_high",
)

STRATEGIES["t1_baseline_volume_high"] = _strat(
    name="t1_baseline_volume_high",
    description="Contrôle négatif : uniquement gros marchés (>250k$ volume). Devrait avoir ~0% ROI car marchés efficients.",
    bankroll=1000,
    zone_or_zones=(0.50, 0.80),
    min_volume=250000,
    bet_size=25, sizing="fixed", priority="price_high",
)

STRATEGIES["t1_baseline_contrarian"] = _strat(
    name="t1_baseline_contrarian",
    description="Contrôle : zone ultra-safe 10-35% YES. Beaucoup de wins mais petit gain par trade.",
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
    description="Zone 40-80% YES, volume <100k$ uniquement. Mise adaptative (5-25$ selon volume). Priorité aux petits marchés.",
    bankroll=1000,
    zone_or_zones=(0.40, 0.80),
    max_volume=100000,
    sizing="adaptive", priority="volume_low",
)

STRATEGIES["t2_micro_vol"] = _strat(
    name="t2_micro_vol",
    description="Zone 30-65% YES, volume <50k$ uniquement. Cible les micro-marchés peu suivis. Mise adaptative.",
    bankroll=1000,
    zone_or_zones=(0.30, 0.65),
    max_volume=50000,
    sizing="adaptive", priority="volume_low",
)

STRATEGIES["t2_noseries"] = _strat(
    name="t2_noseries",
    description="Zone 40-80% YES, exclut les marchés 'series' (récurrents). Teste si les séries diluent le signal.",
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
    description="2 zones selon volume : <100k → 30-65% YES, >100k → 50-80% YES. Teste si adapter la zone au volume aide.",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 100000,       "price_yes_min": 0.30, "price_yes_max": 0.65},
        {"vol_min": 100000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    sizing="adaptive", priority="volume_low",
)

STRATEGIES["t3_mb_3bucket"] = _strat(
    name="t3_mb_3bucket",
    description="3 zones : <25k → 30-60%, 25k-250k → 40-70%, >250k → 50-80%. Plus granulaire que 2 zones.",
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
    description="3 zones + zone morte 100k-250k (ignorée). Exclut les marchés moyens-gros jugés inefficaces.",
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
    description="4 zones très fines (<5k, 5-50k, 50-250k, >250k). Maximum de granularité, risque d'overfitting.",
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
    description="500$ de bankroll, $50/trade, zone 40-80%, sans filtre deadline. Devrait perdre (capital bloqué trop longtemps).",
    bankroll=500,
    zone_or_zones=(0.40, 0.80),
    bet_size=50, sizing="fixed", priority="volume_low",
)

STRATEGIES["t4_cstr_dl60"] = _strat(
    name="t4_cstr_dl60",
    description="500$ bankroll, $50/trade, zone 40-80% + deadline max 60 jours. Test clé : le filtre deadline transforme-t-il la performance ?",
    bankroll=500,
    zone_or_zones=(0.40, 0.80),
    bet_size=50, sizing="fixed", priority="volume_low",
    deadline_max=60,
)

STRATEGIES["t4_cstr_rotation_dl60"] = _strat(
    name="t4_cstr_rotation_dl60",
    description="500$ bankroll, $50/trade, zone 40-80%, deadline 60j. Priorité rotation (préfère les trades qui se résolvent vite).",
    bankroll=500,
    zone_or_zones=(0.40, 0.80),
    bet_size=50, sizing="fixed", priority="rotation",
    deadline_max=60,
)

STRATEGIES["t4_cstr_adaptive_dl90"] = _strat(
    name="t4_cstr_adaptive_dl90",
    description="1000$ bankroll, zone 40-80%, deadline 90j, mise adaptative (5-25$ selon volume). Plus diversifié que les $50 fixes.",
    bankroll=1000,
    zone_or_zones=(0.40, 0.80),
    sizing="adaptive", priority="volume_low",
    deadline_max=90,
)

STRATEGIES["t4_cstr_mb3_dl90"] = _strat(
    name="t4_cstr_mb3_dl90",
    description="1000$ bankroll, 3 zones volume, deadline 90j, mise adaptative. Combine multi-zone et filtre temporel.",
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
    description="Candidat prudent : 2 zones, ignore >250k$, max 2 positions/événement, mise adaptative. Risque minimal.",
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
    description="Candidat équilibré : 3 zones volume, deadline 90j, rotation prioritaire, mise adaptative. Bon compromis risque/rendement.",
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
    description="Candidat rapide : 500$ bankroll, 2 zones, deadline 60j, rotation. Maximise la vitesse de rotation du capital.",
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
    description="Candidat agressif : 1000$ bankroll, 3 zones, $50/trade fixe, deadline 90j. Maximum de rendement, drawdown élevé accepté.",
    bankroll=1000,
    zone_or_zones=[
        {"vol_min": 0,      "vol_max": 25000,        "price_yes_min": 0.30, "price_yes_max": 0.60},
        {"vol_min": 25000,   "vol_max": 250000,       "price_yes_min": 0.40, "price_yes_max": 0.70},
        {"vol_min": 250000,  "vol_max": float("inf"), "price_yes_min": 0.50, "price_yes_max": 0.80},
    ],
    bet_size=50, sizing="fixed", priority="volume_low",
    deadline_max=90,
)

# ─────────────────────────────────────────────────────────────────────────────
# LIVE TEST — Micro trades to validate the pipeline
# ─────────────────────────────────────────────────────────────────────────────

STRATEGIES["test_live"] = {
    "name": "Test Live",
    "mode": "live",
    "description": "Micro $1 trades to validate live trading pipeline. Max 4 positions.",
    "bet_side": "NO",
    "price_yes_min": 0.20,
    "price_yes_max": 0.60,
    "min_volume": 10000,
    "max_volume": float("inf"),
    "max_total_exposure_pct": 1.00,
    "max_cluster_exposure_pct": 1.00,
    "bet_size": 1.0,
    "bankroll": 4.0,
    "entry_cost_rate": 0.03,
    "portfolio_file": "portfolio_test_live.json",
    "sizing": "fixed",
    "priority": "price_high",
    "deadline_min": 3,
    "deadline_max": None,
    "event_cap": 3,
    "exclude_series": False,
}



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

    # Live trading
    "live": ["test_live"],
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
