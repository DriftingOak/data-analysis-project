"""
POLYMARKET BOT - Paper Trading Module
=====================================
Simulates trading without real money.
Persists state to portfolio.json between runs.
Supports multiple strategies with separate portfolios.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

import config
import strategies as strat_config

PORTFOLIO_FILE = "portfolio.json"  # Default, can be overridden

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PaperPosition:
    market_id: str
    question: str
    token_id: str
    bet_side: str  # "YES" or "NO"
    entry_date: str
    entry_price: float  # Price we paid (e.g., 0.75 for NO when YES=25%)
    size_usd: float  # Amount in USD
    shares: float  # Number of shares bought
    cluster: str
    expected_close: str  # Expected resolution date
    status: str  # "open" or "closed"
    resolution: Optional[str] = None  # "win", "lose", or None
    close_date: Optional[str] = None
    pnl: Optional[float] = None
    current_price: Optional[float] = None  # Current price (updated each run)
    price_yes_current: Optional[float] = None  # Current YES price


@dataclass
class PaperPortfolio:
    bankroll_initial: float
    bankroll_current: float
    entry_cost_rate: float
    positions: List[PaperPosition]
    closed_trades: List[PaperPosition]
    created_at: str
    last_updated: str
    
    # Stats
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0


# =============================================================================
# PERSISTENCE
# =============================================================================

def load_portfolio(portfolio_file: str = PORTFOLIO_FILE, 
                   initial_bankroll: float = None,
                   entry_cost_rate: float = None) -> PaperPortfolio:
    """Load portfolio from JSON file, or create new one."""
    
    # Use defaults from config/strategies if not specified
    if initial_bankroll is None:
        initial_bankroll = getattr(strat_config, 'INITIAL_BANKROLL', config.BANKROLL)
    if entry_cost_rate is None:
        entry_cost_rate = getattr(config, 'PAPER_ENTRY_COST_RATE', 0.03)
    
    print(f"[DEBUG] Looking for portfolio file: {portfolio_file}")
    print(f"[DEBUG] File exists: {os.path.exists(portfolio_file)}")
    
    if os.path.exists(portfolio_file):
        try:
            with open(portfolio_file, "r") as f:
                data = json.load(f)
            
            # Reconstruct positions
            positions = [PaperPosition(**p) for p in data.get("positions", [])]
            closed_trades = [PaperPosition(**p) for p in data.get("closed_trades", [])]
            
            print(f"[DEBUG] Loaded existing portfolio: {len(positions)} open, {len(closed_trades)} closed")
            
            return PaperPortfolio(
                bankroll_initial=data["bankroll_initial"],
                bankroll_current=data["bankroll_current"],
                entry_cost_rate=data["entry_cost_rate"],
                positions=positions,
                closed_trades=closed_trades,
                created_at=data["created_at"],
                last_updated=data["last_updated"],
                total_trades=data.get("total_trades", 0),
                wins=data.get("wins", 0),
                losses=data.get("losses", 0),
                total_pnl=data.get("total_pnl", 0.0),
            )
        except Exception as e:
            print(f"[WARN] Could not load portfolio from {portfolio_file}: {e}, creating new one")
    
    print(f"[DEBUG] Creating NEW portfolio (file not found)")
    
    # Create new portfolio
    now = datetime.now().isoformat()
    return PaperPortfolio(
        bankroll_initial=initial_bankroll,
        bankroll_current=initial_bankroll,
        entry_cost_rate=entry_cost_rate,
        positions=[],
        closed_trades=[],
        created_at=now,
        last_updated=now,
    )


def save_portfolio(portfolio: PaperPortfolio, portfolio_file: str = PORTFOLIO_FILE):
    """Save portfolio to JSON file."""
    portfolio.last_updated = datetime.now().isoformat()
    
    data = {
        "bankroll_initial": portfolio.bankroll_initial,
        "bankroll_current": portfolio.bankroll_current,
        "entry_cost_rate": portfolio.entry_cost_rate,
        "positions": [asdict(p) for p in portfolio.positions],
        "closed_trades": [asdict(p) for p in portfolio.closed_trades],
        "created_at": portfolio.created_at,
        "last_updated": portfolio.last_updated,
        "total_trades": portfolio.total_trades,
        "wins": portfolio.wins,
        "losses": portfolio.losses,
        "total_pnl": portfolio.total_pnl,
    }
    
    with open(portfolio_file, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"[INFO] Portfolio saved to {portfolio_file}")


# =============================================================================
# PAPER TRADING LOGIC
# =============================================================================

def get_open_exposure(portfolio: PaperPortfolio) -> tuple[float, Dict[str, float]]:
    """Calculate current exposure from open positions."""
    total = 0.0
    by_cluster = {}
    
    for pos in portfolio.positions:
        if pos.status == "open":
            total += pos.size_usd
            by_cluster[pos.cluster] = by_cluster.get(pos.cluster, 0) + pos.size_usd
    
    return total, by_cluster


def get_open_market_ids(portfolio: PaperPortfolio) -> set:
    """Get set of market IDs we already have positions in."""
    return {pos.market_id for pos in portfolio.positions if pos.status == "open"}


def paper_buy(
    portfolio: PaperPortfolio,
    market_id: str,
    question: str,
    token_id: str,
    bet_side: str,
    entry_price: float,
    size_usd: float,
    cluster: str,
    expected_close: str,
) -> Optional[PaperPosition]:
    """Simulate buying a position."""
    
    # Check if we have enough cash
    exposure_total, _ = get_open_exposure(portfolio)
    available_cash = portfolio.bankroll_current - exposure_total
    
    if size_usd > available_cash:
        print(f"[PAPER] Insufficient cash: need ${size_usd:.2f}, have ${available_cash:.2f}")
        return None
    
    # Apply entry cost (simulated spread + slippage)
    effective_investment = size_usd * (1 - portfolio.entry_cost_rate)
    shares = effective_investment / entry_price
    
    position = PaperPosition(
        market_id=market_id,
        question=question,
        token_id=token_id,
        bet_side=bet_side,
        entry_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        entry_price=entry_price,
        size_usd=size_usd,
        shares=shares,
        cluster=cluster,
        expected_close=expected_close,
        status="open",
    )
    
    portfolio.positions.append(position)
    portfolio.total_trades += 1
    
    print(f"[PAPER] Bought {bet_side} @ {entry_price:.1%} for ${size_usd:.2f} ({shares:.2f} shares)")
    print(f"        Market: {question[:60]}...")
    
    return position


def check_resolution(market_data: Dict) -> Optional[str]:
    """Check if a market has been resolved and return outcome.
    
    Returns:
        "yes" if YES won, "no" if NO won, None if not resolved
    """
    import json as json_lib
    
    # Check if market is closed/resolved
    is_closed = market_data.get("closed") == True or market_data.get("closed") == "true"
    is_resolved = market_data.get("resolved") == True or market_data.get("resolved") == "true"
    
    if not (is_closed or is_resolved):
        return None
    
    # Method 1: Check "outcome" field directly
    outcome = market_data.get("outcome")
    if outcome is not None:
        outcome_str = str(outcome).lower()
        if outcome_str in ["yes", "1", "true"]:
            return "yes"
        elif outcome_str in ["no", "0", "false"]:
            return "no"
    
    # Method 2: Check "resolutionSource" or similar fields
    resolution = market_data.get("resolutionSource") or market_data.get("resolution")
    if resolution:
        resolution_str = str(resolution).lower()
        if "yes" in resolution_str:
            return "yes"
        elif "no" in resolution_str:
            return "no"
    
    # Method 3: Check outcomePrices - if one is 1.0 and other is 0.0
    prices_raw = market_data.get("outcomePrices", "")
    outcomes_raw = market_data.get("outcomes", "")
    
    try:
        if isinstance(prices_raw, str) and prices_raw:
            prices = json_lib.loads(prices_raw)
        else:
            prices = prices_raw or []
        
        if isinstance(outcomes_raw, str) and outcomes_raw:
            outcomes = json_lib.loads(outcomes_raw)
        else:
            outcomes = outcomes_raw or []
        
        if len(prices) >= 2:
            # Check if prices indicate resolution (one is ~1, other is ~0)
            p0, p1 = float(prices[0]), float(prices[1])
            if p0 >= 0.99 and p1 <= 0.01:
                # First outcome won - check if it's "Yes"
                if outcomes and len(outcomes) > 0:
                    if str(outcomes[0]).lower() == "yes":
                        return "yes"
                    else:
                        return "no"  # First outcome won but wasn't "Yes"
                return "yes"  # Default: first outcome = yes
            elif p1 >= 0.99 and p0 <= 0.01:
                # Second outcome won - check if it's "No"
                if outcomes and len(outcomes) > 1:
                    if str(outcomes[1]).lower() == "no":
                        return "no"
                    else:
                        return "yes"  # Second outcome won but wasn't "No"
                return "no"  # Default: second outcome = no
    except Exception as e:
        pass
    
    # Market is closed but we couldn't determine outcome
    # This might happen for cancelled markets
    return None


def settle_position(position: PaperPosition, outcome: str) -> float:
    """Settle a position and calculate P&L.
    
    Args:
        position: The position to settle
        outcome: "yes" or "no" (which side won)
    
    Returns:
        P&L in USD
    """
    # Determine if we won
    if position.bet_side == "NO":
        won = (outcome == "no")
    else:
        won = (outcome == "yes")
    
    if won:
        # We get $1 per share
        payout = position.shares
        pnl = payout - position.size_usd
        position.resolution = "win"
    else:
        # We get nothing
        payout = 0
        pnl = -position.size_usd
        position.resolution = "lose"
    
    position.status = "closed"
    position.close_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    position.pnl = pnl
    
    return pnl


def update_current_prices(portfolio: PaperPortfolio, market_lookup: Dict[str, Any]):
    """Update current prices for all open positions.
    
    Args:
        portfolio: The portfolio to update
        market_lookup: Dict mapping market_id to market data
    """
    import json as json_lib
    
    for pos in portfolio.positions:
        if pos.status != "open":
            continue
        
        market_data = market_lookup.get(pos.market_id)
        if not market_data:
            continue
        
        try:
            # Parse prices
            prices_raw = market_data.get("outcomePrices", "")
            outcomes_raw = market_data.get("outcomes", "")
            
            if isinstance(prices_raw, str) and prices_raw:
                prices = json_lib.loads(prices_raw)
            else:
                prices = prices_raw or []
            
            if isinstance(outcomes_raw, str) and outcomes_raw:
                outcomes = json_lib.loads(outcomes_raw)
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
            
            if price_yes is not None:
                pos.price_yes_current = price_yes
                if pos.bet_side == "NO":
                    pos.current_price = 1 - price_yes
                else:
                    pos.current_price = price_yes
        except Exception as e:
            pass


def update_portfolio_stats(portfolio: PaperPortfolio):
    """Recalculate portfolio statistics."""
    portfolio.wins = sum(1 for t in portfolio.closed_trades if t.resolution == "win")
    portfolio.losses = sum(1 for t in portfolio.closed_trades if t.resolution == "lose")
    portfolio.total_pnl = sum(t.pnl for t in portfolio.closed_trades if t.pnl is not None)
    portfolio.bankroll_current = portfolio.bankroll_initial + portfolio.total_pnl


# =============================================================================
# REPORTING
# =============================================================================

def print_portfolio_summary(portfolio: PaperPortfolio, strategy_name: str = ""):
    """Print a summary of the portfolio."""
    exposure_total, exposure_by_cluster = get_open_exposure(portfolio)
    
    print("\n" + "=" * 60)
    if strategy_name:
        print(f"PAPER PORTFOLIO: {strategy_name}")
    else:
        print("PAPER PORTFOLIO SUMMARY")
    print("=" * 60)
    print(f"Started: {portfolio.created_at[:10]}")
    print(f"Last updated: {portfolio.last_updated[:10]}")
    print(f"Entry cost rate: {portfolio.entry_cost_rate:.1%}")
    print("-" * 60)
    print(f"Initial bankroll: ${portfolio.bankroll_initial:,.2f}")
    print(f"Current bankroll: ${portfolio.bankroll_current:,.2f}")
    print(f"Total P&L: ${portfolio.total_pnl:+,.2f} ({portfolio.total_pnl/portfolio.bankroll_initial:+.1%})")
    print("-" * 60)
    print(f"Total trades: {portfolio.total_trades}")
    print(f"Closed: {len(portfolio.closed_trades)} (W:{portfolio.wins} / L:{portfolio.losses})")
    print(f"Win rate: {portfolio.wins / len(portfolio.closed_trades) * 100:.1f}%" if portfolio.closed_trades else "Win rate: N/A")
    print(f"Open positions: {len([p for p in portfolio.positions if p.status == 'open'])}")
    print(f"Current exposure: ${exposure_total:,.2f} ({exposure_total/portfolio.bankroll_current*100:.1f}%)")
    
    if exposure_by_cluster:
        print("\nExposure by cluster:")
        for cluster, exp in sorted(exposure_by_cluster.items(), key=lambda x: -x[1]):
            print(f"  {cluster}: ${exp:,.2f}")
    
    print("=" * 60)


def print_open_positions(portfolio: PaperPortfolio):
    """Print list of open positions."""
    open_pos = [p for p in portfolio.positions if p.status == "open"]
    
    if not open_pos:
        print("\n[INFO] No open positions")
        return
    
    print(f"\n{'='*60}")
    print(f"OPEN POSITIONS ({len(open_pos)})")
    print("=" * 60)
    
    for pos in sorted(open_pos, key=lambda x: x.entry_date):
        print(f"  [{pos.cluster}] {pos.bet_side} @ {pos.entry_price:.1%} | ${pos.size_usd:.0f} | {pos.entry_date[:10]}")
        print(f"      {pos.question[:55]}...")


def print_recent_trades(portfolio: PaperPortfolio, n: int = 10):
    """Print recent closed trades."""
    recent = sorted(portfolio.closed_trades, key=lambda x: x.close_date or "", reverse=True)[:n]
    
    if not recent:
        print("\n[INFO] No closed trades yet")
        return
    
    print(f"\n{'='*60}")
    print(f"RECENT CLOSED TRADES (last {n})")
    print("=" * 60)
    
    for trade in recent:
        emoji = "✅" if trade.resolution == "win" else "❌"
        print(f"  {emoji} {trade.bet_side} | P&L: ${trade.pnl:+.2f} | {trade.close_date[:10]}")
        print(f"      {trade.question[:55]}...")
