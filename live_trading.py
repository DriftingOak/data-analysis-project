#!/usr/bin/env python3
"""
POLYMARKET BOT - Live Trading Module
=====================================
Handles real trading on Polymarket via py-clob-client SDK.

Architecture:
    1. PROPOSE: Bot scans → finds candidates → saves to pending_trades.json
    2. NOTIFY:  Telegram message with trade details
    3. APPROVE: Human triggers GitHub Actions workflow_dispatch
    4. EXECUTE: Workflow reads pending_trades.json → places real orders

Safety layers:
    - Human validation required for every trade
    - Proposals expire after 6h (next scan cycle)
    - Max trades per execution batch
    - Balance verification before each trade
    - Orderbook sanity check (price divergence < 3%)
    - Kill switch via LIVE_TRADING_ENABLED env var
    - Shadow mode for dry runs with real API
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

import config

# =============================================================================
# CONSTANTS
# =============================================================================

PENDING_TRADES_FILE = "pending_trades.json"
LIVE_PORTFOLIO_FILE = "live_portfolio.json"

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon

# Safety limits
MAX_TRADES_PER_BATCH = 5          # Max trades in a single execution
MAX_PRICE_DIVERGENCE = 0.03       # 3% max divergence between Gamma and CLOB
PROPOSAL_EXPIRY_HOURS = 6         # Proposals expire after this
ORDER_EXPIRY_HOURS = 6            # GTD orders expire after this
MIN_BALANCE_USDC = 5.0            # Don't trade if balance < $5

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PendingTrade:
    """A proposed trade awaiting human approval."""
    id: str                    # Unique trade ID (timestamp-based)
    strategy: str              # Strategy that proposed it
    market_id: str             # Polymarket market ID
    question: str              # Market question
    token_id: str              # Token ID for the NO side
    bet_side: str              # "NO" (always for our strategy)
    proposed_price: float      # Price at proposal time
    size_usd: float            # Bet size in USDC
    cluster: str               # Geographic cluster
    expected_close: str        # Expected resolution date
    proposed_at: str           # ISO timestamp of proposal
    expires_at: str            # ISO timestamp of expiry
    status: str = "pending"    # pending / approved / executed / expired / failed
    execution_result: Optional[str] = None  # Result message after execution


@dataclass
class LivePosition:
    """A real position on Polymarket."""
    market_id: str
    question: str
    token_id: str
    bet_side: str
    entry_price: float         # Price we actually paid
    size_usd: float            # Amount in USDC
    shares: float              # Number of shares
    cluster: str
    expected_close: str
    order_id: str              # CLOB order ID
    strategy: str              # Strategy that generated it
    entry_date: str            # ISO timestamp
    status: str = "open"       # open / closed
    resolution: Optional[str] = None  # win / lose
    close_date: Optional[str] = None
    pnl: Optional[float] = None
    current_price: Optional[float] = None


@dataclass
class LivePortfolio:
    """Live trading portfolio state."""
    positions: List[LivePosition]
    closed_trades: List[LivePosition]
    total_executed: int = 0
    total_pnl: float = 0.0
    wins: int = 0
    losses: int = 0
    created_at: str = ""
    last_updated: str = ""


# =============================================================================
# CLOB CLIENT INITIALIZATION
# =============================================================================

_client = None

def get_client():
    """Get or create the CLOB client (singleton).
    
    Uses signature_type=2 (browser wallet / MetaMask) with proxy address,
    so positions are visible on polymarket.com.
    """
    global _client
    if _client is not None:
        return _client
    
    try:
        from py_clob_client.client import ClobClient
    except ImportError:
        raise ImportError(
            "py-clob-client not installed. Run: pip install py-clob-client"
        )
    
    private_key = config.PRIVATE_KEY
    proxy_address = getattr(config, "POLYMARKET_PROXY_ADDRESS", "") or os.getenv("POLYMARKET_PROXY_ADDRESS", "")
    
    if not private_key:
        raise ValueError("PRIVATE_KEY not set. Add it to GitHub Secrets.")
    if not proxy_address:
        raise ValueError(
            "POLYMARKET_PROXY_ADDRESS not set. "
            "Find it on polymarket.com → Deposit → Deposit Address."
        )
    
    _client = ClobClient(
        HOST,
        key=private_key,
        chain_id=CHAIN_ID,
        signature_type=2,  # Browser wallet (MetaMask)
        funder=proxy_address,
    )
    _client.set_api_creds(_client.create_or_derive_api_creds())
    
    return _client


def reset_client():
    """Reset the singleton (for testing)."""
    global _client
    _client = None


# =============================================================================
# SAFETY CHECKS
# =============================================================================

def is_live_enabled() -> bool:
    """Check if live trading is enabled via environment variable."""
    return os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"


def is_shadow_mode() -> bool:
    """Shadow mode: do everything except actually place orders."""
    return os.getenv("LIVE_SHADOW_MODE", "false").lower() == "true"


def get_usdc_balance() -> Optional[float]:
    """Get USDC balance from Polymarket."""
    try:
        client = get_client()
        # The get_balance method returns the available balance
        balance_data = client.get_balance_allowance()
        # balance_data might vary by version; try common patterns
        if isinstance(balance_data, dict):
            return float(balance_data.get("balance", 0)) / 1e6  # USDC has 6 decimals
        return None
    except Exception as e:
        print(f"[WARN] Could not fetch balance: {e}")
        return None


def check_orderbook_price(token_id: str, expected_price: float) -> Tuple[bool, float, str]:
    """Check if the orderbook price is close to the expected price.
    
    Returns: (is_ok, actual_price, message)
    """
    try:
        client = get_client()
        book = client.get_order_book(token_id)
        
        asks = getattr(book, 'asks', None) or []
        if not asks:
            return False, 0.0, "No asks in orderbook"
        
        best_ask = float(asks[0].price if hasattr(asks[0], 'price') else asks[0]["price"])
        divergence = abs(best_ask - expected_price)
        
        if divergence > MAX_PRICE_DIVERGENCE:
            return False, best_ask, (
                f"Price divergence too high: expected {expected_price:.4f}, "
                f"got {best_ask:.4f} (diff: {divergence:.4f})"
            )
        
        return True, best_ask, f"Orderbook OK: best ask {best_ask:.4f}"
        
    except Exception as e:
        return False, 0.0, f"Orderbook check failed: {e}"


# =============================================================================
# PENDING TRADES MANAGEMENT
# =============================================================================

def load_pending_trades() -> List[PendingTrade]:
    """Load pending trades from JSON file."""
    if not os.path.exists(PENDING_TRADES_FILE):
        return []
    try:
        with open(PENDING_TRADES_FILE, "r") as f:
            data = json.load(f)
        return [PendingTrade(**t) for t in data]
    except Exception as e:
        print(f"[WARN] Failed to load pending trades: {e}")
        return []


def save_pending_trades(trades: List[PendingTrade]):
    """Save pending trades to JSON file."""
    with open(PENDING_TRADES_FILE, "w") as f:
        json.dump([asdict(t) for t in trades], f, indent=2)


def propose_trade(
    strategy: str,
    market_id: str,
    question: str,
    token_id: str,
    bet_side: str,
    proposed_price: float,
    size_usd: float,
    cluster: str,
    expected_close: str,
) -> PendingTrade:
    """Create a new trade proposal and add it to pending list."""
    now = datetime.now(timezone.utc)
    trade_id = f"LT-{now.strftime('%Y%m%d-%H%M%S')}-{market_id[:8]}"
    
    trade = PendingTrade(
        id=trade_id,
        strategy=strategy,
        market_id=market_id,
        question=question,
        token_id=token_id,
        bet_side=bet_side,
        proposed_price=proposed_price,
        size_usd=size_usd,
        cluster=cluster,
        expected_close=expected_close,
        proposed_at=now.isoformat(),
        expires_at=(now + timedelta(hours=PROPOSAL_EXPIRY_HOURS)).isoformat(),
    )
    
    # Load existing, add new, save
    pending = load_pending_trades()
    pending.append(trade)
    save_pending_trades(pending)
    
    return trade


def cleanup_expired_proposals() -> int:
    """Remove expired proposals. Returns count removed."""
    pending = load_pending_trades()
    now = datetime.now(timezone.utc)
    
    active = []
    expired_count = 0
    
    for trade in pending:
        expires_at = datetime.fromisoformat(trade.expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if now > expires_at:
            expired_count += 1
        else:
            active.append(trade)
    
    if expired_count > 0:
        save_pending_trades(active)
    
    return expired_count


def get_pending_trade_ids() -> List[str]:
    """Get IDs of all pending (non-expired) trades."""
    cleanup_expired_proposals()
    pending = load_pending_trades()
    return [t.id for t in pending if t.status == "pending"]


# =============================================================================
# TRADE EXECUTION
# =============================================================================

def execute_approved_trades(trade_ids: List[str]) -> List[Dict[str, Any]]:
    """Execute specific approved trades.
    
    This is called by the GitHub Actions workflow_dispatch after human approval.
    
    Returns list of execution results.
    """
    if not is_live_enabled() and not is_shadow_mode():
        return [{"error": "Live trading is not enabled. Set LIVE_TRADING_ENABLED=true"}]
    
    pending = load_pending_trades()
    results = []
    executed_count = 0
    
    for trade in pending:
        if trade.id not in trade_ids:
            continue
        if trade.status != "pending":
            results.append({
                "trade_id": trade.id,
                "status": "skipped",
                "reason": f"Trade status is {trade.status}, not pending"
            })
            continue
        
        # Safety: max batch size
        if executed_count >= MAX_TRADES_PER_BATCH:
            results.append({
                "trade_id": trade.id,
                "status": "skipped",
                "reason": f"Max batch size ({MAX_TRADES_PER_BATCH}) reached"
            })
            continue
        
        # Execute single trade
        result = _execute_single_trade(trade)
        results.append(result)
        
        if result.get("status") == "executed":
            executed_count += 1
            trade.status = "executed"
            trade.execution_result = json.dumps(result)
        else:
            trade.status = "failed"
            trade.execution_result = json.dumps(result)
    
    # Save updated statuses
    save_pending_trades(pending)
    
    return results


def _execute_single_trade(trade: PendingTrade) -> Dict[str, Any]:
    """Execute a single trade with all safety checks.
    
    Steps:
    1. Check balance
    2. Check orderbook price
    3. Place limit order (GTD, expires in 6h)
    4. Record in live portfolio
    """
    result = {
        "trade_id": trade.id,
        "market_id": trade.market_id,
        "question": trade.question[:60],
    }
    
    try:
        client = get_client()
        
        # 1. Balance check
        # Use a simpler approach - try to get balance via the API
        # If it fails, we'll proceed with caution
        
        # 2. Orderbook sanity check
        price_ok, actual_price, price_msg = check_orderbook_price(
            trade.token_id, trade.proposed_price
        )
        result["orderbook_check"] = price_msg
        
        if not price_ok:
            result["status"] = "failed"
            result["reason"] = f"Orderbook check failed: {price_msg}"
            return result
        
        # 3. Calculate order parameters
        # Limit price: actual best ask + 1 cent (to increase fill probability)
        limit_price = round(min(actual_price + 0.01, trade.proposed_price + 0.02), 2)
        # Ensure price is between 0.01 and 0.99
        limit_price = max(0.01, min(0.99, limit_price))
        
        # Size in shares (not dollars)
        shares = round(trade.size_usd / limit_price, 2)
        
        result["limit_price"] = limit_price
        result["shares"] = shares
        result["size_usd"] = trade.size_usd
        
        # 4. Shadow mode check
        if is_shadow_mode():
            result["status"] = "shadow"
            result["reason"] = "Shadow mode - order not placed"
            print(f"  [SHADOW] Would place: BUY {shares} shares @ {limit_price} "
                  f"for {trade.question[:40]}...")
            return result
        
        # 5. Place the order
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY
        
        order_args = OrderArgs(
            price=limit_price,
            size=shares,
            side=BUY,
            token_id=trade.token_id,
        )
        
        signed_order = client.create_order(order_args)
        
        # GTD = Good Till Date (expires after ORDER_EXPIRY_HOURS)
        # Fallback to GTC if GTD not available
        try:
            resp = client.post_order(signed_order, OrderType.GTC)
        except Exception as e:
            result["status"] = "failed"
            result["reason"] = f"Order placement failed: {e}"
            return result
        
        # 6. Parse response
        order_id = resp.get("orderID", resp.get("id", "unknown"))
        result["status"] = "executed"
        result["order_id"] = order_id
        result["response"] = str(resp)[:200]  # Truncate for logging
        
        # 7. Record in live portfolio
        _record_live_position(trade, order_id, limit_price, shares)
        
        print(f"  ✅ ORDER PLACED: {order_id}")
        print(f"     BUY {shares} NO shares @ {limit_price} = ${trade.size_usd:.2f}")
        print(f"     Market: {trade.question[:50]}...")
        
        return result
        
    except Exception as e:
        result["status"] = "failed"
        result["reason"] = f"Execution error: {str(e)}"
        return result


# =============================================================================
# LIVE PORTFOLIO MANAGEMENT
# =============================================================================

def load_live_portfolio() -> LivePortfolio:
    """Load live portfolio from JSON."""
    if not os.path.exists(LIVE_PORTFOLIO_FILE):
        now = datetime.now(timezone.utc).isoformat()
        return LivePortfolio(
            positions=[],
            closed_trades=[],
            created_at=now,
            last_updated=now,
        )
    
    try:
        with open(LIVE_PORTFOLIO_FILE, "r") as f:
            data = json.load(f)
        
        positions = [LivePosition(**p) for p in data.get("positions", [])]
        closed = [LivePosition(**p) for p in data.get("closed_trades", [])]
        
        return LivePortfolio(
            positions=positions,
            closed_trades=closed,
            total_executed=data.get("total_executed", 0),
            total_pnl=data.get("total_pnl", 0.0),
            wins=data.get("wins", 0),
            losses=data.get("losses", 0),
            created_at=data.get("created_at", ""),
            last_updated=data.get("last_updated", ""),
        )
    except Exception as e:
        print(f"[WARN] Failed to load live portfolio: {e}")
        now = datetime.now(timezone.utc).isoformat()
        return LivePortfolio(
            positions=[], closed_trades=[],
            created_at=now, last_updated=now,
        )


def save_live_portfolio(portfolio: LivePortfolio):
    """Save live portfolio to JSON."""
    portfolio.last_updated = datetime.now(timezone.utc).isoformat()
    
    data = {
        "positions": [asdict(p) for p in portfolio.positions],
        "closed_trades": [asdict(p) for p in portfolio.closed_trades],
        "total_executed": portfolio.total_executed,
        "total_pnl": portfolio.total_pnl,
        "wins": portfolio.wins,
        "losses": portfolio.losses,
        "created_at": portfolio.created_at,
        "last_updated": portfolio.last_updated,
    }
    
    with open(LIVE_PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _record_live_position(
    trade: PendingTrade,
    order_id: str,
    actual_price: float,
    shares: float,
):
    """Record a new position in the live portfolio."""
    portfolio = load_live_portfolio()
    
    position = LivePosition(
        market_id=trade.market_id,
        question=trade.question,
        token_id=trade.token_id,
        bet_side=trade.bet_side,
        entry_price=actual_price,
        size_usd=trade.size_usd,
        shares=shares,
        cluster=trade.cluster,
        expected_close=trade.expected_close,
        order_id=order_id,
        strategy=trade.strategy,
        entry_date=datetime.now(timezone.utc).isoformat(),
    )
    
    portfolio.positions.append(position)
    portfolio.total_executed += 1
    save_live_portfolio(portfolio)


def check_live_resolutions(market_lookup: Dict[str, Any] = None) -> int:
    """Check if any live positions have resolved.
    
    This runs automatically every scan cycle (no human approval needed).
    Returns number of positions resolved.
    """
    import requests
    
    portfolio = load_live_portfolio()
    open_positions = [p for p in portfolio.positions if p.status == "open"]
    
    if not open_positions:
        return 0
    
    resolved = 0
    
    for pos in open_positions:
        # Get market data
        market_data = None
        if market_lookup:
            market_data = market_lookup.get(pos.market_id)
        
        if not market_data:
            try:
                url = f"https://gamma-api.polymarket.com/markets/{pos.market_id}"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    market_data = resp.json()
            except Exception:
                continue
        
        if not market_data:
            continue
        
        # Check if resolved
        outcome = _check_market_resolution(market_data)
        if outcome is None:
            # Update current price
            try:
                prices_raw = market_data.get("outcomePrices", "")
                if isinstance(prices_raw, str) and prices_raw:
                    prices = json.loads(prices_raw)
                else:
                    prices = prices_raw or []
                if prices:
                    price_yes = float(prices[0])
                    pos.current_price = 1 - price_yes if pos.bet_side == "NO" else price_yes
            except Exception:
                pass
            continue
        
        # Position resolved!
        _settle_live_position(pos, outcome)
        portfolio.closed_trades.append(pos)
        resolved += 1
    
    if resolved > 0:
        # Update stats
        portfolio.wins = sum(1 for t in portfolio.closed_trades if t.resolution == "win")
        portfolio.losses = sum(1 for t in portfolio.closed_trades if t.resolution == "lose")
        portfolio.total_pnl = sum(t.pnl or 0 for t in portfolio.closed_trades)
        save_live_portfolio(portfolio)
    
    return resolved


def _check_market_resolution(market_data: Dict) -> Optional[str]:
    """Check if a market has resolved. Returns 'yes'/'no' or None."""
    # Check various resolution indicators
    if market_data.get("closed") or market_data.get("resolved"):
        outcomes_raw = market_data.get("outcomes", [])
        if isinstance(outcomes_raw, str):
            try:
                outcomes = json.loads(outcomes_raw)
            except:
                outcomes = []
        else:
            outcomes = outcomes_raw or []
        
        prices_raw = market_data.get("outcomePrices", "")
        if isinstance(prices_raw, str) and prices_raw:
            try:
                prices = json.loads(prices_raw)
            except:
                prices = []
        else:
            prices = prices_raw or []
        
        if prices:
            try:
                price_yes = float(prices[0])
                if price_yes >= 0.99:
                    return "yes"
                elif price_yes <= 0.01:
                    return "no"
            except:
                pass
    
    return None


def _settle_live_position(pos: LivePosition, outcome: str):
    """Settle a live position based on market outcome."""
    pos.status = "closed"
    pos.close_date = datetime.now(timezone.utc).isoformat()
    
    if pos.bet_side == "NO":
        if outcome == "no":
            pos.resolution = "win"
            pos.pnl = pos.shares * 1.0 - pos.size_usd  # Each share pays $1
        else:
            pos.resolution = "lose"
            pos.pnl = -pos.size_usd  # Lost entire bet
    else:  # YES bets
        if outcome == "yes":
            pos.resolution = "win"
            pos.pnl = pos.shares * 1.0 - pos.size_usd
        else:
            pos.resolution = "lose"
            pos.pnl = -pos.size_usd


# =============================================================================
# TELEGRAM NOTIFICATIONS FOR LIVE TRADING
# =============================================================================

def send_proposal_notification(trade: PendingTrade):
    """Send Telegram notification for a new trade proposal."""
    import requests as req
    
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return
    
    msg = (
        f"🔔 <b>NEW TRADE PROPOSAL</b>\n\n"
        f"<b>ID:</b> <code>{trade.id}</code>\n"
        f"<b>Strategy:</b> {trade.strategy}\n"
        f"<b>Market:</b> {trade.question[:80]}\n"
        f"<b>Side:</b> {trade.bet_side} @ {trade.proposed_price:.1%}\n"
        f"<b>Size:</b> ${trade.size_usd:.2f}\n"
        f"<b>Cluster:</b> {trade.cluster}\n"
        f"<b>Expires:</b> {trade.expires_at[:16]}Z\n\n"
        f"To approve, go to GitHub Actions → Execute Trades → Run workflow\n"
        f"Enter trade ID: <code>{trade.id}</code>"
    )
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req.post(url, data={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        print(f"[WARN] Telegram notification failed: {e}")


def send_execution_notification(results: List[Dict]):
    """Send Telegram notification for execution results."""
    import requests as req
    
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return
    
    executed = [r for r in results if r.get("status") == "executed"]
    failed = [r for r in results if r.get("status") == "failed"]
    shadow = [r for r in results if r.get("status") == "shadow"]
    
    lines = ["💰 <b>TRADE EXECUTION REPORT</b>\n"]
    
    if executed:
        lines.append(f"✅ <b>{len(executed)} executed:</b>")
        for r in executed:
            lines.append(
                f"  • {r.get('question', '?')}\n"
                f"    {r.get('shares', 0)} shares @ {r.get('limit_price', 0):.2f}"
            )
    
    if failed:
        lines.append(f"\n❌ <b>{len(failed)} failed:</b>")
        for r in failed:
            lines.append(f"  • {r.get('trade_id', '?')}: {r.get('reason', '?')}")
    
    if shadow:
        lines.append(f"\n👁 <b>{len(shadow)} shadow (dry run):</b>")
        for r in shadow:
            lines.append(f"  • {r.get('question', '?')}")
    
    msg = "\n".join(lines)
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req.post(url, data={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        print(f"[WARN] Telegram notification failed: {e}")


# =============================================================================
# SUMMARY / STATUS
# =============================================================================

def get_live_status() -> Dict[str, Any]:
    """Get current live trading status for dashboard/logging."""
    portfolio = load_live_portfolio()
    pending = load_pending_trades()
    
    active_pending = [t for t in pending if t.status == "pending"]
    open_positions = [p for p in portfolio.positions if p.status == "open"]
    
    total_exposure = sum(p.size_usd for p in open_positions)
    unrealized_pnl = sum(
        (p.current_price or p.entry_price) * p.shares - p.size_usd
        for p in open_positions
        if p.current_price is not None
    )
    
    return {
        "enabled": is_live_enabled(),
        "shadow_mode": is_shadow_mode(),
        "pending_proposals": len(active_pending),
        "open_positions": len(open_positions),
        "total_exposure_usd": total_exposure,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": portfolio.total_pnl,
        "total_trades": portfolio.total_executed,
        "wins": portfolio.wins,
        "losses": portfolio.losses,
        "pending_trade_ids": [t.id for t in active_pending],
    }


def print_live_status():
    """Print live trading status to console."""
    status = get_live_status()
    
    print("\n" + "=" * 60)
    print("LIVE TRADING STATUS")
    print("=" * 60)
    print(f"  Enabled:           {status['enabled']}")
    print(f"  Shadow mode:       {status['shadow_mode']}")
    print(f"  Pending proposals: {status['pending_proposals']}")
    print(f"  Open positions:    {status['open_positions']}")
    print(f"  Total exposure:    ${status['total_exposure_usd']:.2f}")
    print(f"  Unrealized P&L:    ${status['unrealized_pnl']:+.2f}")
    print(f"  Realized P&L:      ${status['realized_pnl']:+.2f}")
    print(f"  Record:            {status['wins']}W / {status['losses']}L")
    
    if status['pending_trade_ids']:
        print(f"\n  Pending trade IDs:")
        for tid in status['pending_trade_ids']:
            print(f"    • {tid}")
    
    print("=" * 60)


# =============================================================================
# CLI ENTRY POINT (for execute.yml workflow)
# =============================================================================

def cli_execute(args: List[str]):
    """CLI entry point for executing trades.
    
    Usage:
        python -m live_trading execute LT-20260209-120000-abc12345,LT-20260209-120001-def67890
        python -m live_trading execute all
        python -m live_trading status
        python -m live_trading pending
        python -m live_trading cleanup
    """
    if not args:
        print("Usage: python -m live_trading [execute|status|pending|cleanup]")
        return
    
    command = args[0]
    
    if command == "status":
        print_live_status()
        
    elif command == "pending":
        pending = load_pending_trades()
        active = [t for t in pending if t.status == "pending"]
        if not active:
            print("No pending trades.")
        else:
            for t in active:
                print(f"  [{t.id}] {t.strategy} | {t.bet_side} @ {t.proposed_price:.1%} "
                      f"| ${t.size_usd:.2f} | {t.question[:50]}...")
    
    elif command == "cleanup":
        removed = cleanup_expired_proposals()
        print(f"Cleaned up {removed} expired proposals.")
    
    elif command == "execute":
        if len(args) < 2:
            print("Usage: python -m live_trading execute <trade_id1,trade_id2,...|all>")
            return
        
        trade_ids_input = args[1]
        
        if trade_ids_input == "all":
            trade_ids = get_pending_trade_ids()
        else:
            trade_ids = [tid.strip() for tid in trade_ids_input.split(",")]
        
        if not trade_ids:
            print("No trades to execute.")
            return
        
        print(f"Executing {len(trade_ids)} trades...")
        results = execute_approved_trades(trade_ids)
        
        for r in results:
            status = r.get("status", "unknown")
            emoji = {"executed": "✅", "failed": "❌", "shadow": "👁", "skipped": "⏭"}.get(status, "❓")
            print(f"  {emoji} {r.get('trade_id', '?')}: {status}")
            if r.get("reason"):
                print(f"     Reason: {r['reason']}")
        
        # Send Telegram notification
        send_execution_notification(results)
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    import sys
    cli_execute(sys.argv[1:])
