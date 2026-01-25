#!/usr/bin/env python3
"""
Sell a position by market ID.
Usage: python sell_position.py <market_id>
"""

import json
import sys
import requests
from datetime import datetime


def main():
    if len(sys.argv) < 2:
        print("Usage: python sell_position.py <market_id>")
        sys.exit(1)
    
    market_id = sys.argv[1]
    print(f"🔍 Searching for market ID: {market_id}")
    
    # Find position across all strategies
    strategies = ['conservative', 'balanced', 'aggressive', 'volume_sweet']
    found = None
    
    for strat in strategies:
        filepath = f"portfolio_{strat}.json"
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            for pos in data.get('positions', []):
                if str(pos.get('market_id')) == str(market_id) and pos.get('status') == 'open':
                    found = {
                        'strategy': strat,
                        'filepath': filepath,
                        'data': data,
                        'position': pos
                    }
                    break
            if found:
                break
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"Warning: Error reading {filepath}: {e}")
            continue
    
    if not found:
        print(f"❌ No open position found with market_id: {market_id}")
        sys.exit(1)
    
    pos = found['position']
    data = found['data']
    filepath = found['filepath']
    strat = found['strategy']
    
    question = pos.get('question', 'Unknown')[:60]
    print(f"✅ Found in {strat}: {question}...")
    
    # Fetch current price
    print("📊 Fetching current price...")
    try:
        resp = requests.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}",
            timeout=10
        )
        market = resp.json()
        
        prices_raw = market.get('outcomePrices', '')
        if isinstance(prices_raw, str) and prices_raw:
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw or []
        
        current_yes = float(prices[0]) if prices else None
    except Exception as e:
        print(f"❌ Error fetching price: {e}")
        sys.exit(1)
    
    if current_yes is None:
        print("❌ Could not get current price")
        sys.exit(1)
    
    # Calculate P&L
    entry_price = pos.get('entry_price', 0)
    shares = pos.get('shares', 0)
    size_usd = pos.get('size_usd', 0)
    bet_side = pos.get('bet_side', 'NO')
    entry_cost_rate = data.get('entry_cost_rate', 0.03)
    
    current_no = 1 - current_yes
    if bet_side == 'NO':
        sale_value = current_no * shares
    else:
        sale_value = current_yes * shares
    
    exit_fee = sale_value * entry_cost_rate
    net_proceeds = sale_value - exit_fee
    pnl = net_proceeds - size_usd
    
    entry_yes = 1 - entry_price
    print("")
    print(f"📈 Entry YES:    {entry_yes:.1%}")
    print(f"📉 Current YES:  {current_yes:.1%}")
    print(f"💰 P&L:          ${pnl:+.2f}")
    print("")
    
    # Update position
    pos['status'] = 'closed'
    pos['close_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    pos['resolution'] = 'win' if pnl > 0 else 'lose'
    pos['pnl'] = pnl
    
    # Move to closed trades
    if 'closed_trades' not in data:
        data['closed_trades'] = []
    data['closed_trades'].append(pos)
    
    # Remove from positions (keep only open ones or different market_id)
    data['positions'] = [
        p for p in data['positions'] 
        if not (str(p.get('market_id')) == str(market_id) and p.get('status') == 'closed')
    ]
    
    # Update stats
    wins = sum(1 for t in data['closed_trades'] if t.get('resolution') == 'win')
    losses = sum(1 for t in data['closed_trades'] if t.get('resolution') == 'lose')
    total_pnl = sum(t.get('pnl', 0) for t in data['closed_trades'] if t.get('pnl') is not None)
    
    data['wins'] = wins
    data['losses'] = losses
    data['total_pnl'] = total_pnl
    data['bankroll_current'] = data['bankroll_initial'] + total_pnl
    data['last_updated'] = datetime.now().isoformat()
    
    # Save
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"✅ Position sold!")
    print(f"💵 New bankroll: ${data['bankroll_current']:.2f}")


if __name__ == "__main__":
    main()
