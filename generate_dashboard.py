"""
POLYMARKET BOT - Dashboard Generator
====================================
Generates a visual HTML dashboard from portfolio data.
"""

import json
import os
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional

def load_portfolio(filepath: str) -> dict:
    """Load a portfolio JSON file."""
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        return json.load(f)

def fetch_current_prices(market_ids: List[str]) -> Dict[str, float]:
    """Fetch current YES prices for a list of market IDs."""
    prices = {}
    
    print(f"[INFO] Fetching prices for {len(market_ids)} markets...")
    
    # Fetch each market individually by ID
    for i, market_id in enumerate(market_ids):
        try:
            url = f"https://gamma-api.polymarket.com/markets/{market_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            market = resp.json()
            
            # Parse YES price
            prices_raw = market.get("outcomePrices", "")
            outcomes_raw = market.get("outcomes", "")
            
            if isinstance(prices_raw, str) and prices_raw:
                price_list = json.loads(prices_raw)
            else:
                price_list = prices_raw or []
            
            if isinstance(outcomes_raw, str) and outcomes_raw:
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw or []
            
            # Find YES price
            price_yes = None
            for j, outcome in enumerate(outcomes):
                if isinstance(outcome, str) and outcome.lower() == "yes" and j < len(price_list):
                    price_yes = float(price_list[j])
                    break
            
            if price_yes is None and len(price_list) >= 1:
                price_yes = float(price_list[0])
            
            if price_yes is not None:
                prices[market_id] = price_yes
            
            # Progress indicator
            if (i + 1) % 50 == 0:
                print(f"[INFO] Fetched {i + 1}/{len(market_ids)} markets...")
            
            time.sleep(0.02)  # Rate limiting
            
        except Exception as e:
            pass
    
    print(f"[INFO] Got prices for {len(prices)}/{len(market_ids)} markets")
    return prices

def generate_dashboard():
    """Generate HTML dashboard from all portfolio files."""
    
    # Find all portfolio files
    portfolios = {}
    strategy_names = {
        "conservative": "🛡️ Conservative",
        "balanced": "⚖️ Balanced", 
        "aggressive": "🔥 Aggressive",
        "volume_sweet": "📊 Volume Sweet Spot",
    }
    
    # Collect all market IDs we need prices for
    all_market_ids = set()
    
    for strat_key, strat_name in strategy_names.items():
        filepath = f"portfolio_{strat_key}.json"
        data = load_portfolio(filepath)
        if data:
            portfolios[strat_key] = {
                "name": strat_name,
                "data": data
            }
            for pos in data.get("positions", []):
                if pos.get("status") == "open":
                    all_market_ids.add(pos.get("market_id"))
    
    if not portfolios:
        print("[WARN] No portfolio files found")
        return
    
    # Fetch current prices
    current_prices = fetch_current_prices(list(all_market_ids))
    print(f"[INFO] Got prices for {len(current_prices)} markets")
    
    # Generate HTML
    html = generate_html(portfolios, current_prices)
    
    # Write to file
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"[INFO] Dashboard generated: dashboard.html")

def generate_html(portfolios: Dict, current_prices: Dict[str, float]) -> str:
    """Generate the HTML content."""
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Calculate summary stats
    cards_html = ""
    positions_html = ""
    closed_html = ""
    
    for strat_key, strat_info in portfolios.items():
        name = strat_info["name"]
        data = strat_info["data"]
        
        # Stats
        initial = data.get("bankroll_initial", 0)
        current = data.get("bankroll_current", 0)
        pnl = data.get("total_pnl", 0)
        wins = data.get("wins", 0)
        losses = data.get("losses", 0)
        total_trades = data.get("total_trades", 0)
        
        positions = [p for p in data.get("positions", []) if p.get("status") == "open"]
        closed = data.get("closed_trades", [])
        
        roi_pct = (pnl / initial * 100) if initial > 0 else 0
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        # Calculate unrealized P&L
        unrealized_pnl = 0
        for pos in positions:
            market_id = pos.get("market_id")
            if market_id in current_prices:
                current_yes = current_prices[market_id]
                entry_price = pos.get("entry_price", 0)
                shares = pos.get("shares", 0)
                bet_side = pos.get("bet_side", "NO")
                
                if bet_side == "NO":
                    current_no = 1 - current_yes
                    unrealized_pnl += (current_no - entry_price) * shares
                else:
                    unrealized_pnl += (current_yes - entry_price) * shares
        
        # Exposure by cluster
        exposure_by_cluster = {}
        total_exposure = 0
        for pos in positions:
            cluster = pos.get("cluster", "other")
            size = pos.get("size_usd", 0)
            exposure_by_cluster[cluster] = exposure_by_cluster.get(cluster, 0) + size
            total_exposure += size
        
        # Card color based on P&L
        total_pnl_with_unrealized = pnl + unrealized_pnl
        if total_pnl_with_unrealized > 0:
            card_class = "card-positive"
            pnl_class = "positive"
        elif total_pnl_with_unrealized < 0:
            card_class = "card-negative"
            pnl_class = "negative"
        else:
            card_class = ""
            pnl_class = ""
        
        unrealized_class = "positive" if unrealized_pnl > 0 else "negative" if unrealized_pnl < 0 else ""
        
        # Strategy card
        cards_html += f"""
        <div class="card {card_class}">
            <h2>{name}</h2>
            <div class="stats-grid">
                <div class="stat">
                    <span class="stat-value">${current:,.0f}</span>
                    <span class="stat-label">Bankroll</span>
                </div>
                <div class="stat">
                    <span class="stat-value {pnl_class}">${pnl:+,.0f}</span>
                    <span class="stat-label">Realized P&L ({roi_pct:+.1f}%)</span>
                </div>
                <div class="stat">
                    <span class="stat-value {unrealized_class}">${unrealized_pnl:+,.0f}</span>
                    <span class="stat-label">Unrealized P&L</span>
                </div>
                <div class="stat">
                    <span class="stat-value">{win_rate:.0f}%</span>
                    <span class="stat-label">Win Rate ({wins}W/{losses}L)</span>
                </div>
            </div>
            <div class="exposure-bar">
                <div class="exposure-fill" style="width: {min(total_exposure/current*100, 100):.0f}%"></div>
            </div>
            <span class="exposure-label">Exposure: ${total_exposure:,.0f} ({total_exposure/current*100:.0f}%)</span>
            <div class="cluster-tags">
                {"".join(f'<span class="tag tag-{c}">{c}: ${v:.0f}</span>' for c, v in sorted(exposure_by_cluster.items(), key=lambda x: -x[1]))}
            </div>
        </div>
        """
        
        # Open positions table - ALL positions, not limited
        if positions:
            positions_html += f"""
            <div class="section">
                <h3>{name} - Open Positions ({len(positions)})</h3>
                <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Market</th>
                            <th>Side</th>
                            <th>Entry</th>
                            <th>Current</th>
                            <th>Δ</th>
                            <th>Size</th>
                            <th>Cluster</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for pos in sorted(positions, key=lambda x: x.get("entry_date", ""), reverse=True):
                market_id = pos.get("market_id")
                entry_price = pos.get("entry_price", 0)
                bet_side = pos.get("bet_side", "NO")
                shares = pos.get("shares", 0)
                
                # Get current price
                current_yes = current_prices.get(market_id)
                if current_yes is not None:
                    if bet_side == "NO":
                        current_price = 1 - current_yes
                    else:
                        current_price = current_yes
                    
                    delta = current_price - entry_price
                    delta_pnl = delta * shares
                    delta_class = "positive" if delta > 0 else "negative" if delta < 0 else ""
                    current_str = f"{current_price:.0%}"
                    delta_str = f'<span class="{delta_class}">{delta:+.0%} (${delta_pnl:+.0f})</span>'
                else:
                    current_str = "—"
                    delta_str = "—"
                
                positions_html += f"""
                        <tr>
                            <td class="market-name" title="{pos.get('question', '')}">{pos.get("question", "")[:55]}...</td>
                            <td><span class="badge badge-{pos.get('bet_side', '').lower()}">{pos.get("bet_side", "")}</span></td>
                            <td>{entry_price:.0%}</td>
                            <td>{current_str}</td>
                            <td>{delta_str}</td>
                            <td>${pos.get("size_usd", 0):.0f}</td>
                            <td><span class="tag tag-{pos.get('cluster', 'other')}">{pos.get("cluster", "")}</span></td>
                            <td>{pos.get("entry_date", "")[:10]}</td>
                        </tr>
                """
            positions_html += """
                    </tbody>
                </table>
                </div>
            </div>
            """
        
        # Closed trades table - ALL closed trades
        if closed:
            closed_html += f"""
            <div class="section">
                <h3>{name} - Closed Trades ({len(closed)} total)</h3>
                <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Market</th>
                            <th>Side</th>
                            <th>Result</th>
                            <th>P&L</th>
                            <th>Entry</th>
                            <th>Closed</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for trade in sorted(closed, key=lambda x: x.get("close_date", ""), reverse=True):
                result = trade.get("resolution", "")
                pnl_trade = trade.get("pnl", 0)
                result_class = "win" if result == "win" else "lose"
                pnl_class = "positive" if pnl_trade > 0 else "negative"
                
                closed_html += f"""
                        <tr>
                            <td class="market-name" title="{trade.get('question', '')}">{trade.get("question", "")[:55]}...</td>
                            <td><span class="badge badge-{trade.get('bet_side', '').lower()}">{trade.get("bet_side", "")}</span></td>
                            <td><span class="badge badge-{result_class}">{"✅ WIN" if result == "win" else "❌ LOSS"}</span></td>
                            <td class="{pnl_class}">${pnl_trade:+.2f}</td>
                            <td>{trade.get("entry_price", 0):.0%}</td>
                            <td>{trade.get("close_date", "")[:10]}</td>
                        </tr>
                """
            closed_html += """
                    </tbody>
                </table>
                </div>
            </div>
            """
    
    # Full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket Bot Dashboard</title>
    <style>
        :root {{
            --bg-primary: #0f1419;
            --bg-secondary: #1a1f2e;
            --bg-card: #232b3b;
            --text-primary: #e7e9ea;
            --text-secondary: #8b98a5;
            --accent: #1d9bf0;
            --positive: #00c853;
            --negative: #ff5252;
            --border: #2f3947;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}
        
        h1 {{
            font-size: 2rem;
            margin-bottom: 5px;
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
        }}
        
        .card-positive {{
            border-left: 4px solid var(--positive);
        }}
        
        .card-negative {{
            border-left: 4px solid var(--negative);
        }}
        
        .card h2 {{
            font-size: 1.2rem;
            margin-bottom: 15px;
            color: var(--text-primary);
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 15px;
        }}
        
        .stat {{
            display: flex;
            flex-direction: column;
        }}
        
        .stat-value {{
            font-size: 1.3rem;
            font-weight: 600;
        }}
        
        .stat-label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}
        
        .positive {{ color: var(--positive); }}
        .negative {{ color: var(--negative); }}
        
        .exposure-bar {{
            height: 6px;
            background: var(--bg-secondary);
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 5px;
        }}
        
        .exposure-fill {{
            height: 100%;
            background: var(--accent);
            border-radius: 3px;
        }}
        
        .exposure-label {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        
        .cluster-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 10px;
        }}
        
        .tag {{
            font-size: 0.7rem;
            padding: 3px 8px;
            border-radius: 4px;
            background: var(--bg-secondary);
            color: var(--text-secondary);
        }}
        
        .tag-mideast {{ background: #3d2929; color: #ff8a80; }}
        .tag-ukraine {{ background: #2a3d29; color: #b9f6ca; }}
        .tag-china {{ background: #3d3429; color: #ffe57f; }}
        .tag-latam {{ background: #29333d; color: #80d8ff; }}
        .tag-europe {{ background: #35293d; color: #ea80fc; }}
        .tag-africa {{ background: #3d2f29; color: #ffcc80; }}
        .tag-other {{ background: var(--bg-secondary); color: var(--text-secondary); }}
        
        .section {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        
        .section h3 {{
            margin-bottom: 15px;
            font-size: 1rem;
        }}
        
        .table-wrapper {{
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
        }}
        
        th, td {{
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            color: var(--text-secondary);
            font-weight: 500;
            position: sticky;
            top: 0;
            background: var(--bg-secondary);
        }}
        
        .market-name {{
            max-width: 280px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .badge {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 500;
        }}
        
        .badge-no {{ background: #3d2929; color: #ff8a80; }}
        .badge-yes {{ background: #2a3d29; color: #b9f6ca; }}
        .badge-win {{ background: #2a3d29; color: #b9f6ca; }}
        .badge-lose {{ background: #3d2929; color: #ff8a80; }}
        
        tr:hover {{
            background: rgba(255,255,255,0.02);
        }}
        
        @media (max-width: 600px) {{
            .cards {{
                grid-template-columns: 1fr;
            }}
            
            table {{
                font-size: 0.7rem;
            }}
            
            .market-name {{
                max-width: 150px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📈 Polymarket Bot Dashboard</h1>
            <p class="subtitle">Last updated: {now} UTC</p>
        </header>
        
        <div class="cards">
            {cards_html}
        </div>
        
        {closed_html}
        
        {positions_html}
    </div>
</body>
</html>
"""
    
    return html


if __name__ == "__main__":
    generate_dashboard()
