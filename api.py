"""
POLYMARKET BOT - API Wrapper
============================
Handles communication with Polymarket Gamma API and CLOB API.
"""

import requests
import time
import hmac
import hashlib
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import config

# =============================================================================
# GAMMA API (Market data)
# =============================================================================


def _fetch_page(url: str, params: dict) -> List[Dict]:
    """Fetch a single page from Gamma API."""
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] _fetch_page: {e}")
        return []


def fetch_open_markets(limit: int = 500) -> List[Dict]:
    """Fetch open markets from Gamma API (all markets, paginated)."""
    all_markets = []
    offset = 0
    
    while True:
        url = f"{config.GAMMA_API_URL}/markets"
        params = {
            "closed": "false",
            "limit": min(limit, 100),
            "offset": offset,
        }
        
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            markets = resp.json()
            
            if not markets:
                break
            
            all_markets.extend(markets)
            offset += len(markets)
            
            if len(markets) < 100:
                break
                
            time.sleep(0.1)  # Rate limiting
            
        except Exception as e:
            print(f"[ERROR] fetch_open_markets: {e}")
            break
    
    return all_markets


def fetch_geo_markets_fast(max_workers: int = 5) -> List[Dict]:
    """Fetch all open markets with parallel pagination.
    
    ~10x faster than fetch_open_markets by parallelizing page requests.
    """
    url = f"{config.GAMMA_API_URL}/markets"
    
    # First page to confirm API is up
    first_page = _fetch_page(url, {"closed": "false", "limit": 100, "offset": 0})
    if not first_page:
        return []
    
    all_markets = list(first_page)
    
    if len(first_page) < 100:
        return all_markets
    
    # Generate all offsets (estimate ~28000 markets)
    offsets = list(range(100, 30000, 100))
    
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_page, url, {"closed": "false", "limit": 100, "offset": o}): o
            for o in offsets
        }
        
        for future in as_completed(futures):
            page = future.result()
            if page:
                all_markets.extend(page)
    
    return all_markets


def fetch_market_by_id(market_id: str) -> Optional[Dict]:
    """Fetch single market details."""
    url = f"{config.GAMMA_API_URL}/markets/{market_id}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] fetch_market_by_id({market_id}): {e}")
        return None


# =============================================================================
# CLOB API (Trading)
# =============================================================================

def get_clob_headers(method: str, path: str, body: str = "") -> Dict[str, str]:
    """Generate authenticated headers for CLOB API."""
    timestamp = str(int(time.time()))
    
    message = timestamp + method.upper() + path + body
    signature = hmac.new(
        base64.b64decode(config.POLYMARKET_SECRET),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    
    return {
        "POLY_API_KEY": config.POLYMARKET_API_KEY,
        "POLY_SIGNATURE": signature_b64,
        "POLY_TIMESTAMP": timestamp,
        "POLY_PASSPHRASE": config.POLYMARKET_PASSPHRASE,
        "Content-Type": "application/json",
    }


def get_orderbook(token_id: str) -> Optional[Dict]:
    """Get orderbook for a token."""
    url = f"{config.CLOB_API_URL}/book"
    params = {"token_id": token_id}
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] get_orderbook({token_id}): {e}")
        return None


def get_best_price(token_id: str, side: str = "BUY") -> Optional[float]:
    """Get best available price for a token.
    
    Args:
        token_id: The token to check
        side: "BUY" or "SELL"
    
    Returns:
        Best price or None
    """
    book = get_orderbook(token_id)
    if not book:
        return None
    
    if side == "BUY":
        # Best ask (lowest sell price)
        asks = book.get("asks", [])
        if asks:
            return float(asks[0].get("price", 0))
    else:
        # Best bid (highest buy price)
        bids = book.get("bids", [])
        if bids:
            return float(bids[0].get("price", 0))
    
    return None


def get_account_balance() -> Optional[float]:
    """Get USDC balance from CLOB API."""
    if not config.POLYMARKET_API_KEY:
        print("[WARN] No API key configured, returning mock balance")
        return config.BANKROLL
    
    path = "/balance"
    headers = get_clob_headers("GET", path)
    
    try:
        resp = requests.get(
            f"{config.CLOB_API_URL}{path}",
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("balance", 0))
    except Exception as e:
        print(f"[ERROR] get_account_balance: {e}")
        return None


def get_open_positions() -> List[Dict]:
    """Get current open positions."""
    if not config.POLYMARKET_API_KEY:
        return []
    
    path = "/positions"
    headers = get_clob_headers("GET", path)
    
    try:
        resp = requests.get(
            f"{config.CLOB_API_URL}{path}",
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] get_open_positions: {e}")
        return []


def place_market_order(
    token_id: str,
    side: str,
    size: float,
    dry_run: bool = True
) -> Optional[Dict]:
    """Place a market order.
    
    Args:
        token_id: The token to trade
        side: "BUY" or "SELL"
        size: Amount in USDC
        dry_run: If True, don't actually place the order
    
    Returns:
        Order result or None
    """
    if dry_run:
        print(f"[DRY RUN] Would place {side} order for ${size:.2f} on {token_id}")
        return {"dry_run": True, "token_id": token_id, "side": side, "size": size}
    
    if not config.POLYMARKET_API_KEY:
        print("[ERROR] Cannot place order: No API key configured")
        return None
    
    path = "/order"
    body = {
        "tokenID": token_id,
        "side": side,
        "size": str(size),
        "type": "market",
    }
    
    import json
    body_str = json.dumps(body)
    headers = get_clob_headers("POST", path, body_str)
    
    try:
        resp = requests.post(
            f"{config.CLOB_API_URL}{path}",
            headers=headers,
            json=body,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERROR] place_market_order: {e}")
        return None


# =============================================================================
# UTILITIES
# =============================================================================

def get_token_ids(market: Dict) -> Dict[str, str]:
    """Extract YES and NO token IDs from market data."""
    import json
    tokens = {}
    
    # Try clobTokenIds first - may be JSON string
    clob_ids_raw = market.get("clobTokenIds", [])
    if isinstance(clob_ids_raw, str):
        try:
            clob_ids = json.loads(clob_ids_raw) if clob_ids_raw else []
        except:
            clob_ids = []
    else:
        clob_ids = clob_ids_raw or []
    
    # outcomes may also be JSON string
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
                outcome_lower = outcome.lower()
                if outcome_lower == "yes":
                    tokens["YES"] = clob_ids[i]
                elif outcome_lower == "no":
                    tokens["NO"] = clob_ids[i]
    
    # Fallback for binary markets without Yes/No labels
    if not tokens and len(clob_ids) == 2:
        tokens["YES"] = clob_ids[0]
        tokens["NO"] = clob_ids[1]
    
    return tokens


def parse_market_timestamps(market: Dict) -> Dict[str, Optional[float]]:
    """Parse market timestamps."""
    def parse_ts(key: str) -> Optional[float]:
        val = market.get(key)
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                # Try ISO format
                dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                return dt.timestamp()
            except:
                pass
            try:
                # Try Unix timestamp string
                return float(val)
            except:
                pass
        return None
    
    return {
        "start_ts": parse_ts("startDate") or parse_ts("createdAt"),
        "end_ts": parse_ts("endDate"),
        "close_ts": parse_ts("closedTime") or parse_ts("endDate"),
    }
