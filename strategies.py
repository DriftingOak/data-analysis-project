"""
POLYMARKET BOT - Strategy Definitions
=====================================
Multiple strategies to test in parallel.
Each gets its own portfolio file.

NOTE: Bankroll is set high for paper trading to maximize sample size.
For real trading, adjust to your actual capital.

STRATEGY TYPES:
- Standard: With exposure limits (realistic for live trading)
- Unlimited: No exposure limits (max data collection for backtesting)
- Experimental: New ideas to test
"""

# =============================================================================
# STANDARD STRATEGIES (with exposure limits)
# =============================================================================

STRATEGIES = {
    # -------------------------------------------------------------------------
    # STANDARD - Realistic exposure limits
    # -------------------------------------------------------------------------
    "conservative": {
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
    },
    
    "balanced": {
        "name": "Balanced",
        "description": "Balanced risk/reward - the baseline strategy",
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
    },
    
    "aggressive": {
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
    },
    
    "volume_sweet": {
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
    },
    
    # -------------------------------------------------------------------------
    # UNLIMITED - No exposure limits (for backtesting data collection)
    # -------------------------------------------------------------------------
    "unlimited_balanced": {
        "name": "Unlimited Balanced",
        "description": "Balanced strategy with NO exposure limits - takes every eligible trade",
        "bet_side": "NO",
        "price_yes_min": 0.20,
        "price_yes_max": 0.60,
        "min_volume": 10000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 100.0,  # Effectively unlimited
        "max_cluster_exposure_pct": 100.0,  # Effectively unlimited
        "bet_size": 25.0,
        "bankroll": 50000.0,  # High bankroll to never run out
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_unlimited_balanced.json",
    },
    
    "unlimited_conservative": {
        "name": "Unlimited Conservative",
        "description": "Conservative strategy with NO exposure limits",
        "bet_side": "NO",
        "price_yes_min": 0.10,
        "price_yes_max": 0.25,
        "min_volume": 10000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 100.0,
        "max_cluster_exposure_pct": 100.0,
        "bet_size": 25.0,
        "bankroll": 50000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_unlimited_conservative.json",
    },
    
    "unlimited_aggressive": {
        "name": "Unlimited Aggressive",
        "description": "Aggressive strategy with NO exposure limits",
        "bet_side": "NO",
        "price_yes_min": 0.30,
        "price_yes_max": 0.60,
        "min_volume": 10000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 100.0,
        "max_cluster_exposure_pct": 100.0,
        "bet_size": 25.0,
        "bankroll": 50000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_unlimited_aggressive.json",
    },
    
    "unlimited_wide": {
        "name": "Unlimited Wide",
        "description": "Very wide range (10-70%) with NO limits - maximum data collection",
        "bet_side": "NO",
        "price_yes_min": 0.10,
        "price_yes_max": 0.70,
        "min_volume": 5000,  # Lower volume threshold too
        "max_volume": float("inf"),
        "max_total_exposure_pct": 100.0,
        "max_cluster_exposure_pct": 100.0,
        "bet_size": 25.0,
        "bankroll": 100000.0,  # Extra high for max coverage
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_unlimited_wide.json",
    },
    
    # -------------------------------------------------------------------------
    # EXPERIMENTAL - New ideas to test
    # -------------------------------------------------------------------------
    "high_volume_only": {
        "name": "High Volume Only",
        "description": "Only trade markets with >$100k volume - max liquidity",
        "bet_side": "NO",
        "price_yes_min": 0.20,
        "price_yes_max": 0.60,
        "min_volume": 100000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 0.80,
        "max_cluster_exposure_pct": 0.30,
        "bet_size": 50.0,  # Bigger bets on liquid markets
        "bankroll": 10000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_high_volume.json",
    },
    
    "micro_bets": {
        "name": "Micro Bets",
        "description": "Small $10 bets, wide diversification",
        "bet_side": "NO",
        "price_yes_min": 0.15,
        "price_yes_max": 0.55,
        "min_volume": 5000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 0.90,  # Can use more capital with small bets
        "max_cluster_exposure_pct": 0.15,  # But diversify more
        "bet_size": 10.0,
        "bankroll": 3000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_micro_bets.json",
    },
    
    "contrarian_yes": {
        "name": "Contrarian YES",
        "description": "Bet YES when NO is 70-90% - contrarian play",
        "bet_side": "YES",
        "price_yes_min": 0.10,  # YES at 10-30%
        "price_yes_max": 0.30,
        "min_volume": 15000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 0.40,  # More conservative
        "max_cluster_exposure_pct": 0.15,
        "bet_size": 20.0,
        "bankroll": 5000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_contrarian_yes.json",
    },
    
    "tight_spread": {
        "name": "Tight Spread",
        "description": "Narrow 35-50% range - tighter edge, higher conviction",
        "bet_side": "NO",
        "price_yes_min": 0.35,
        "price_yes_max": 0.50,
        "min_volume": 20000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 0.70,
        "max_cluster_exposure_pct": 0.25,
        "bet_size": 35.0,
        "bankroll": 5000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_tight_spread.json",
    },
    
    "low_volume_gems": {
        "name": "Low Volume Gems",
        "description": "Target overlooked markets with $5k-$20k volume",
        "bet_side": "NO",
        "price_yes_min": 0.20,
        "price_yes_max": 0.50,
        "min_volume": 5000,
        "max_volume": 20000,
        "max_total_exposure_pct": 0.50,
        "max_cluster_exposure_pct": 0.15,
        "bet_size": 15.0,  # Smaller bets on less liquid
        "bankroll": 3000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_low_volume_gems.json",
    },
    
    "mideast_focus": {
        "name": "Mideast Focus",
        "description": "Only Middle East cluster - regional specialization",
        "bet_side": "NO",
        "price_yes_min": 0.20,
        "price_yes_max": 0.60,
        "min_volume": 10000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 0.80,
        "max_cluster_exposure_pct": 0.80,  # High since it's cluster-specific
        "bet_size": 25.0,
        "bankroll": 3000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_mideast_focus.json",
        "cluster_filter": ["mideast"],  # Custom filter
    },
    
    "europe_focus": {
        "name": "Europe Focus", 
        "description": "Only Eastern Europe cluster - Ukraine/Russia focused",
        "bet_side": "NO",
        "price_yes_min": 0.20,
        "price_yes_max": 0.60,
        "min_volume": 10000,
        "max_volume": float("inf"),
        "max_total_exposure_pct": 0.80,
        "max_cluster_exposure_pct": 0.80,
        "bet_size": 25.0,
        "bankroll": 3000.0,
        "entry_cost_rate": 0.03,
        "portfolio_file": "portfolio_europe_focus.json",
        "cluster_filter": ["eastern_europe"],
    },
}

# =============================================================================
# STRATEGY GROUPS (for running subsets)
# =============================================================================

STRATEGY_GROUPS = {
    "standard": ["conservative", "balanced", "aggressive", "volume_sweet"],
    "unlimited": ["unlimited_balanced", "unlimited_conservative", "unlimited_aggressive", "unlimited_wide"],
    "experimental": ["high_volume_only", "micro_bets", "contrarian_yes", "tight_spread", "low_volume_gems"],
    "regional": ["mideast_focus", "europe_focus"],
    "all": list(STRATEGIES.keys()),
    
    # Curated sets
    "quick": ["balanced", "unlimited_balanced"],  # Fast test
    "full_backtest": ["unlimited_balanced", "unlimited_conservative", "unlimited_aggressive", "unlimited_wide"],
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


def list_strategies() -> list:
    """List all available strategy names."""
    return list(STRATEGIES.keys())


def list_groups() -> list:
    """List all strategy group names."""
    return list(STRATEGY_GROUPS.keys())


def print_strategies():
    """Print all strategies with descriptions."""
    print("\n" + "=" * 70)
    print("AVAILABLE STRATEGIES")
    print("=" * 70)
    
    # Group by type
    groups = [
        ("Standard (with limits)", ["conservative", "balanced", "aggressive", "volume_sweet"]),
        ("Unlimited (no limits)", ["unlimited_balanced", "unlimited_conservative", "unlimited_aggressive", "unlimited_wide"]),
        ("Experimental", ["high_volume_only", "micro_bets", "contrarian_yes", "tight_spread", "low_volume_gems", "mideast_focus", "europe_focus"]),
    ]
    
    for group_name, strat_names in groups:
        print(f"\n{group_name}:")
        print("-" * 50)
        for name in strat_names:
            if name in STRATEGIES:
                s = STRATEGIES[name]
                side = s.get("bet_side", "NO")
                pmin = s.get("price_yes_min", 0) * 100
                pmax = s.get("price_yes_max", 1) * 100
                vol = s.get("min_volume", 0)
                print(f"  {name:25} | {side} {pmin:.0f}-{pmax:.0f}% | Vol>${vol/1000:.0f}k")
    
    print("\n" + "=" * 70)
    print("STRATEGY GROUPS (use with --paper <group>)")
    print("=" * 70)
    for group, members in STRATEGY_GROUPS.items():
        print(f"  {group:15} -> {', '.join(members[:4])}{'...' if len(members) > 4 else ''}")


if __name__ == "__main__":
    print_strategies()
