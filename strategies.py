"""
POLYMARKET BOT - Strategy Definitions
=====================================
Multiple strategies to test in parallel.
Each gets its own portfolio file.

NOTE: Bankroll is set high for paper trading to maximize sample size.
For real trading, adjust to your actual capital.
"""

STRATEGIES = {
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
    },
}

def get_strategy(name: str) -> dict:
    """Get strategy config by name."""
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGIES.keys())}")
    return STRATEGIES[name]

def list_strategies() -> list:
    """List all available strategy names."""
    return list(STRATEGIES.keys())
