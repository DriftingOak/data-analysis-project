#!/usr/bin/env python3
"""
POLYMARKET BOT - Dashboard Generator
====================================
Generates a visual HTML dashboard from portfolio data.
Dynamically loads all strategies from strategies.py.
"""

import json
import os
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional

# Try to import strategies for dynamic loading
try:
    import strategies as strat_config
    DYNAMIC_STRATEGIES = True
except ImportError:
    DYNAMIC_STRATEGIES = False
    print("[WARN] Could not import strategies module, using static list")


def get_strategy_names() -> Dict[str, str]:
    """Get all strategy names with display names."""
    if DYNAMIC_STRATEGIES:
        # Build from strategies.py
        names = {}
        emojis = {
            "conservative": "🛡️",
            "balanced": "⚖️",
            "aggressive": "🔥",
            "volume_sweet": "📊",
            "unlimited": "♾️",
            "high_volume": "📈",
            "micro": "🔬",
            "contrarian": "🔄",
            "tight": "🎯",
            "low_volume": "💎",
            "mideast": "🌍",
            "europe": "🇪🇺",
        }
        
        for key, params in strat_config.STRATEGIES.items():
            # Find matching emoji
            emoji = "📋"
            for prefix, e in emojis.items():
                if prefix in key:
                    emoji = e
                    break
            
            names[key] = f"{emoji} {params.get('name', key)}"
        
        return names
    else:
        # Fallback static list
        return {
            "conservative": "🛡️ Conservative",
            "balanced": "⚖️ Balanced",
            "aggressive": "🔥 Aggressive",
            "volume_sweet": "📊 Volume Sweet Spot",
        }


def get_strategy_description(key: str) -> str:
    """Get strategy description."""
    if DYNAMIC_STRATEGIES and key in strat_config.STRATEGIES:
        params = strat_config.STRATEGIES[key]
        side = params.get("bet_side", "NO")
        pmin = params.get("price_yes_min", 0) * 100
        pmax = params.get("price_yes_max", 1) * 100
        return f"Bet {side} on YES {pmin:.0f}-{pmax:.0f}%"
    
    # Fallback
    static_desc = {
        "conservative": "Bet NO on YES 10-25%",
        "balanced": "Bet NO on YES 20-60%",
        "aggressive": "Bet NO on YES 30-60%",
        "volume_sweet": "Bet NO on YES 20-60%, Vol $15k-100k",
    }
    return static_desc.get(key, "")


def load_portfolio(filepath: str) -> dict:
    """Load a portfolio JSON file."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Error loading {filepath}: {e}")
        return None


def fetch_market_data(market_ids: List[str]) -> Dict[str, dict]:
    """Fetch current data for a list of market IDs."""
    markets = {}
    
    if not market_ids:
        return markets
    
    print(f"[INFO] Fetching data for {len(market_ids)} markets...")
    
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
            
            markets[market_id] = {
                "price_yes": price_yes,
                "slug": market.get("slug", ""),
                "closed": market.get("closed", False),
                "question": market.get("question", ""),
            }
            
            if (i + 1) % 50 == 0:
                print(f"[INFO] Fetched {i + 1}/{len(market_ids)} markets...")
            
            time.sleep(0.02)
            
        except Exception as e:
            pass
    
    print(f"[INFO] Got data for {len(markets)}/{len(market_ids)} markets")
    return markets


def generate_dashboard():
    """Generate HTML dashboard from all portfolio files."""
    
    # Get all strategy names dynamically
    strategy_names = get_strategy_names()
    
    portfolios = {}
    all_market_ids = set()
    
    for strat_key, strat_name in strategy_names.items():
        # Try different filename patterns
        filepath = f"portfolio_{strat_key}.json"
        
        data = load_portfolio(filepath)
        if data:
            portfolios[strat_key] = {
                "name": strat_name,
                "data": data
            }
            for pos in data.get("positions", []):
                all_market_ids.add(pos.get("market_id"))
            for pos in data.get("closed_trades", []):
                all_market_ids.add(pos.get("market_id"))
    
    if not portfolios:
        print("[WARN] No portfolio files found")
        # Create empty dashboard anyway
        html = generate_empty_dashboard()
        with open("dashboard.html", "w", encoding="utf-8") as f:
            f.write(html)
        return
    
    print(f"[INFO] Loaded {len(portfolios)} portfolios")
    
    market_data = fetch_market_data(list(all_market_ids))
    
    html = generate_html(portfolios, market_data)
    
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"[INFO] Dashboard generated: dashboard.html")


def generate_empty_dashboard() -> str:
    """Generate an empty dashboard when no portfolios exist."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Polymarket Bot - Dashboard</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; text-align: center; padding: 100px 20px; }}
        h1 {{ color: #00d4ff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Polymarket Bot</h1>
        <p>No portfolios found yet. Run the bot to start paper trading!</p>
        <p style="color: #888;">Last updated: {now}</p>
    </div>
</body>
</html>"""


def generate_html(portfolios: Dict, market_data: Dict[str, dict]) -> str:
    """Generate the HTML content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    cards_html = ""
    positions_html = ""
    closed_html = ""
    
    # Sort portfolios: standard first, then unlimited, then experimental
    def sort_key(item):
        key = item[0]
        if key in ["conservative", "balanced", "aggressive", "volume_sweet"]:
            return (0, key)
        elif "unlimited" in key:
            return (1, key)
        else:
            return (2, key)
    
    sorted_portfolios = sorted(portfolios.items(), key=sort_key)
    
    for strat_key, strat_info in sorted_portfolios:
        name = strat_info["name"]
        data = strat_info["data"]
        
        initial = data.get("bankroll_initial", 0)
        current = data.get("bankroll_current", 0)
        pnl = data.get("total_pnl", 0)
        wins = data.get("wins", 0)
        losses = data.get("losses", 0)
        
        positions = [p for p in data.get("positions", []) if p.get("status") == "open"]
        closed = data.get("closed_trades", [])
        
        roi_pct = (pnl / initial * 100) if initial > 0 else 0
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        # Calculate unrealized P&L
        unrealized_pnl = 0
        for pos in positions:
            market_id = pos.get("market_id")
            mkt = market_data.get(market_id)
            if mkt and mkt.get("price_yes") is not None:
                current_yes = mkt["price_yes"]
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
        
        # Card colors
        total_pnl_display = pnl + unrealized_pnl
        if total_pnl_display > 0:
            card_class = "card-positive"
        elif total_pnl_display < 0:
            card_class = "card-negative"
        else:
            card_class = ""
        
        pnl_class = "positive" if pnl > 0 else "negative" if pnl < 0 else ""
        unrealized_class = "positive" if unrealized_pnl > 0 else "negative" if unrealized_pnl < 0 else ""
        
        strategy_desc = get_strategy_description(strat_key)
        
        cards_html += f"""
        <div class="card {card_class}">
            <h2>{name}</h2>
            <p class="strategy-desc">{strategy_desc}</p>
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
                <div class="exposure-fill" style="width: {min(total_exposure/current*100 if current > 0 else 0, 100):.0f}%"></div>
            </div>
            <span class="exposure-label">Exposure: ${total_exposure:,.0f} ({total_exposure/current*100 if current > 0 else 0:.0f}%)</span>
            <div class="cluster-tags">
                {"".join(f'<span class="tag tag-{c}">{c}: ${v:.0f}</span>' for c, v in sorted(exposure_by_cluster.items(), key=lambda x: -x[1]))}
            </div>
        </div>
        """
        
        # Open positions table (simplified)
        if positions:
            table_id = f"table-{strat_key}"
            positions_html += f"""
            <div class="section collapsed" data-section="{strat_key}">
                <h3 class="section-header" onclick="toggleSection('{strat_key}')">
                    <span class="toggle-icon">▶</span> {name} - Open Positions ({len(positions)})
                </h3>
                <div class="section-content">
                <table id="{table_id}" class="sortable">
                    <thead>
                        <tr>
                            <th>Market</th>
                            <th>Side</th>
                            <th>Entry</th>
                            <th>Current</th>
                            <th>P&L</th>
                            <th>Cluster</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for pos in sorted(positions, key=lambda x: x.get("entry_date", ""), reverse=True):
                market_id = pos.get("market_id")
                mkt = market_data.get(market_id, {})
                
                entry_no = pos.get("entry_price", 0)
                entry_yes = 1 - entry_no
                current_yes = mkt.get("price_yes") if mkt else None
                
                if current_yes is not None:
                    current_no = 1 - current_yes
                    shares = pos.get("shares", 0)
                    if pos.get("bet_side") == "NO":
                        unrealized = (current_no - entry_no) * shares
                    else:
                        unrealized = (current_yes - entry_yes) * shares
                    current_str = f"{current_yes:.1%}"
                    pnl_str = f"${unrealized:+.0f}"
                    pnl_cls = "positive" if unrealized > 0 else "negative" if unrealized < 0 else ""
                else:
                    current_str = "-"
                    pnl_str = "-"
                    pnl_cls = ""
                
                slug = mkt.get("slug", "")
                link = f"https://polymarket.com/event/{slug}" if slug else f"https://polymarket.com/markets/{market_id}"
                
                positions_html += f"""
                        <tr>
                            <td class="market-name"><a href="{link}" target="_blank">{pos.get('question', '')[:50]}...</a></td>
                            <td>{pos.get('bet_side', 'NO')}</td>
                            <td>{entry_yes:.1%}</td>
                            <td>{current_str}</td>
                            <td class="{pnl_cls}">{pnl_str}</td>
                            <td><span class="tag tag-{pos.get('cluster', 'other')}">{pos.get('cluster', 'other')}</span></td>
                        </tr>
                """
            
            positions_html += """
                    </tbody>
                </table>
                </div>
            </div>
            """
        
        # Closed trades (simplified)
        if closed:
            closed_html += f"""
            <div class="section collapsed" data-section="closed-{strat_key}">
                <h3 class="section-header" onclick="toggleSection('closed-{strat_key}')">
                    <span class="toggle-icon">▶</span> {name} - Closed Trades ({len(closed)})
                </h3>
                <div class="section-content">
                <table class="sortable">
                    <thead>
                        <tr>
                            <th>Market</th>
                            <th>Result</th>
                            <th>P&L</th>
                            <th>Closed</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for trade in sorted(closed, key=lambda x: x.get("close_date", ""), reverse=True)[:20]:
                result = trade.get("resolution", "")
                pnl_trade = trade.get("pnl", 0)
                result_class = "win" if result == "win" else "lose"
                pnl_class = "positive" if pnl_trade > 0 else "negative"
                
                closed_html += f"""
                        <tr>
                            <td class="market-name">{trade.get('question', '')[:50]}...</td>
                            <td class="{result_class}">{'✅' if result == 'win' else '❌'}</td>
                            <td class="{pnl_class}">${pnl_trade:+.0f}</td>
                            <td>{trade.get('close_date', '')[:10]}</td>
                        </tr>
                """
            
            if len(closed) > 20:
                closed_html += f"""
                        <tr><td colspan="4" style="text-align:center; color:#888;">... and {len(closed) - 20} more</td></tr>
                """
            
            closed_html += """
                    </tbody>
                </table>
                </div>
            </div>
            """
    
    # Full HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Polymarket Bot - Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            background: #0f0f1a; 
            color: #e0e0e0; 
            margin: 0; 
            padding: 20px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; margin-bottom: 5px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ 
            background: #1a1a2e; 
            border-radius: 12px; 
            padding: 20px; 
            border: 1px solid #2a2a4a;
        }}
        .card-positive {{ border-left: 4px solid #00ff88; }}
        .card-negative {{ border-left: 4px solid #ff4466; }}
        .card h2 {{ margin: 0 0 5px 0; font-size: 1.1em; color: #fff; }}
        .strategy-desc {{ color: #888; font-size: 0.85em; margin: 0 0 15px 0; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 15px; }}
        .stat {{ text-align: center; }}
        .stat-value {{ display: block; font-size: 1.3em; font-weight: 600; }}
        .stat-label {{ font-size: 0.75em; color: #888; }}
        
        .positive {{ color: #00ff88; }}
        .negative {{ color: #ff4466; }}
        .win {{ color: #00ff88; }}
        .lose {{ color: #ff4466; }}
        
        .exposure-bar {{ background: #2a2a4a; height: 6px; border-radius: 3px; margin: 10px 0 5px 0; }}
        .exposure-fill {{ background: linear-gradient(90deg, #00d4ff, #00ff88); height: 100%; border-radius: 3px; transition: width 0.3s; }}
        .exposure-label {{ font-size: 0.8em; color: #888; }}
        
        .cluster-tags {{ margin-top: 10px; }}
        .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; margin: 2px; background: #2a2a4a; }}
        .tag-mideast {{ background: #4a3a2a; color: #ffaa44; }}
        .tag-eastern_europe {{ background: #3a3a4a; color: #88aaff; }}
        .tag-asia {{ background: #3a4a3a; color: #88ff88; }}
        .tag-latam {{ background: #4a3a4a; color: #ff88ff; }}
        
        .section {{ background: #1a1a2e; border-radius: 8px; margin-bottom: 15px; border: 1px solid #2a2a4a; }}
        .section-header {{ 
            padding: 12px 15px; 
            cursor: pointer; 
            margin: 0;
            font-size: 0.95em;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section-header:hover {{ background: #252540; }}
        .toggle-icon {{ transition: transform 0.2s; font-size: 0.8em; }}
        .section:not(.collapsed) .toggle-icon {{ transform: rotate(90deg); }}
        .section-content {{ display: none; padding: 0 15px 15px 15px; }}
        .section:not(.collapsed) .section-content {{ display: block; }}
        
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
        th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #2a2a4a; }}
        th {{ background: #252540; font-weight: 500; cursor: pointer; }}
        th:hover {{ background: #303050; }}
        .market-name {{ max-width: 300px; }}
        .market-name a {{ color: #00d4ff; text-decoration: none; }}
        .market-name a:hover {{ text-decoration: underline; }}
        
        @media (max-width: 600px) {{
            .stats-grid {{ grid-template-columns: 1fr; }}
            .cards {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Polymarket Geopolitical Bot</h1>
        <p class="subtitle">Last updated: {now} | Auto-refresh: 5 min</p>
        
        <div class="cards">
            {cards_html}
        </div>
        
        <h2 style="color: #00d4ff; margin-top: 40px;">📈 Open Positions</h2>
        {positions_html if positions_html else '<p style="color: #888;">No open positions</p>'}
        
        <h2 style="color: #00d4ff; margin-top: 40px;">📊 Closed Trades</h2>
        {closed_html if closed_html else '<p style="color: #888;">No closed trades yet</p>'}
    </div>
    
    <script>
        function toggleSection(sectionId) {{
            const section = document.querySelector(`[data-section="${{sectionId}}"]`);
            if (section) section.classList.toggle('collapsed');
        }}
    </script>
</body>
</html>
"""
    return html


if __name__ == "__main__":
    generate_dashboard()
