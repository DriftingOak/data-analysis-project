"""Strategy registry for the Polymarket paper-trading bot.

Exports:
- STRATEGIES: dict[str, dict]  (params per strategy)
- STRATEGY_GROUPS: dict[str, list[str]] (named sets of strategies)

Notes:
- Includes a "default" group alias to avoid surprises when workflows pass STRATEGY=default.
- Ensures each strategy has an entry_cost_rate to prevent runtime errors if config is missing it.
"""

from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------
# Defaults (used only if a strategy forgets to set the field)
# ---------------------------------------------------------------------
DEFAULT_ENTRY_COST_RATE = 0.03  # 3% friction (fees+slippage proxy) for paper

# ---------------------------------------------------------------------
# Strategy definitions
# ---------------------------------------------------------------------
STRATEGIES: Dict[str, Dict[str, Any]] = {
    # =========================
    # STANDARD (bounded)
    # =========================
    "conservative": {
        "side": "NO",
        "price_min": 0.02,
        "price_max": 0.12,
        "min_volume": 200_000,
        "max_markets_per_run": 6,
        "entry_cost_rate": 0.03,
    },
    "balanced": {
        "side": "NO",
        "price_min": 0.02,
        "price_max": 0.18,
        "min_volume": 100_000,
        "max_markets_per_run": 10,
        "entry_cost_rate": 0.03,
    },
    "aggressive": {
        "side": "NO",
        "price_min": 0.02,
        "price_max": 0.25,
        "min_volume": 50_000,
        "max_markets_per_run": 14,
        "entry_cost_rate": 0.03,
    },
    "volume_sweet": {
        "side": "NO",
        "price_min": 0.03,
        "price_max": 0.20,
        "min_volume": 300_000,
        "max_markets_per_run": 10,
        "entry_cost_rate": 0.03,
    },

    # =========================
    # UNLIMITED (wide)
    # =========================
    "unlimited_conservative": {
        "side": "NO",
        "price_min": 0.01,
        "price_max": 0.12,
        "min_volume": 50_000,
        "max_markets_per_run": 50,
        "entry_cost_rate": 0.03,
    },
    "unlimited_balanced": {
        "side": "NO",
        "price_min": 0.01,
        "price_max": 0.20,
        "min_volume": 25_000,
        "max_markets_per_run": 75,
        "entry_cost_rate": 0.03,
    },
    "unlimited_aggressive": {
        "side": "NO",
        "price_min": 0.01,
        "price_max": 0.35,
        "min_volume": 15_000,
        "max_markets_per_run": 100,
        "entry_cost_rate": 0.03,
    },
    "unlimited_wide": {
        "side": "NO",
        "price_min": 0.01,
        "price_max": 0.45,
        "min_volume": 10_000,
        "max_markets_per_run": 150,
        "entry_cost_rate": 0.03,
    },

    # =========================
    # EXPERIMENTAL (examples)
    # =========================
    "high_volume_only": {
        "side": "NO",
        "price_min": 0.02,
        "price_max": 0.25,
        "min_volume": 1_000_000,
        "max_markets_per_run": 20,
        "entry_cost_rate": 0.03,
    },
    "micro_bets": {
        "side": "NO",
        "price_min": 0.01,
        "price_max": 0.08,
        "min_volume": 10_000,
        "max_markets_per_run": 200,
        "entry_cost_rate": 0.03,
    },
    "contrarian_yes": {
        "side": "YES",
        "price_min": 0.70,
        "price_max": 0.98,
        "min_volume": 100_000,
        "max_markets_per_run": 15,
        "entry_cost_rate": 0.03,
    },
    "tight_spread": {
        "side": "NO",
        "price_min": 0.02,
        "price_max": 0.20,
        "min_volume": 50_000,
        "max_markets_per_run": 20,
        "max_spread_pct": 0.02,  # 2%
        "entry_cost_rate": 0.03,
    },
    "low_volume_gems": {
        "side": "NO",
        "price_min": 0.02,
        "price_max": 0.15,
        "min_volume": 5_000,
        "max_markets_per_run": 50,
        "entry_cost_rate": 0.03,
    },

    # =========================
    # REGIONAL (examples)
    # =========================
    "mideast_focus": {
        "side": "NO",
        "price_min": 0.02,
        "price_max": 0.25,
        "min_volume": 25_000,
        "max_markets_per_run": 40,
        "cluster_filter": ["mideast"],
        "entry_cost_rate": 0.03,
    },
    "europe_focus": {
        "side": "NO",
        "price_min": 0.02,
        "price_max": 0.25,
        "min_volume": 25_000,
        "max_markets_per_run": 40,
        "cluster_filter": ["europe", "eastern_europe"],
        "entry_cost_rate": 0.03,
    },
}

# Ensure every strategy has entry_cost_rate (prevents fallback-to-config crashes)
for _name, _params in STRATEGIES.items():
    _params.setdefault("entry_cost_rate", DEFAULT_ENTRY_COST_RATE)

# ---------------------------------------------------------------------
# Strategy groups
# ---------------------------------------------------------------------
STRATEGY_GROUPS: Dict[str, List[str]] = {
    "standard": ["conservative", "balanced", "aggressive", "volume_sweet"],
    "unlimited": ["unlimited_balanced", "unlimited_conservative", "unlimited_aggressive", "unlimited_wide"],
    "experimental": ["high_volume_only", "micro_bets", "contrarian_yes", "tight_spread", "low_volume_gems"],
    "regional": ["mideast_focus", "europe_focus"],
    "all": list(STRATEGIES.keys()),

    # Curated sets
    "quick": ["balanced", "unlimited_balanced"],
    "full_backtest": ["unlimited_balanced", "unlimited_conservative", "unlimited_aggressive", "unlimited_wide"],
}

# Alias to keep workflows/CLI stable if they pass "default"
if "default" not in STRATEGY_GROUPS:
    STRATEGY_GROUPS["default"] = STRATEGY_GROUPS["standard"]
