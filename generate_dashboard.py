#!/usr/bin/env python3
"""
POLYMARKET BOT - Dashboard Generator
====================================
Generates a visual HTML dashboard from portfolio data.
Dynamically loads all strategies from strategies.py.

UPDATED: Uses new strategy key names (side, price_min, price_max)
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
            emoji = "📋"
            for prefix, e in emojis.items():
                if prefix in key:
                    emoji = e
                    break
            # Format display name from key
            display_name = key.replace("_", " ").title()
            names[key] = f"{emoji} {display_name}"
        
        return names
    else:
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
        # Use original key names: bet_side, price_yes_min, price_yes_max
        side = params.get("bet_side", "NO")
        pmin = params.get("price_yes_min", 0) * 100
        pmax = params.get("price_yes_max", 1) * 100
        min_vol = params.get("min_volume", 0)
        max_vol = params.get("max_volume", float("inf"))
        
        desc = f"Bet {side} on YES {pmin:.0f}-{pmax:.0f}%"
        if min_vol >= 1_000_000:
            desc += f", Vol>${min_vol/1_000_000:.0f}M"
        elif min_vol >= 1_000:
            desc += f", Vol>${min_vol/1_000:.0f}k"
        
        if max_vol < float("inf"):
            desc += f"-{max_vol/1_000:.0f}k"
        
        return desc
    
    # Fallback static descriptions (original values)
    static_desc = {
        "conservative": "Bet NO on YES 10-25%, Vol>$10k",
        "balanced": "Bet NO on YES 20-60%, Vol>$10k",
        "aggressive": "Bet NO on YES 30-60%, Vol>$10k",
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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    strategy_names = get_strategy_names()
    
    portfolios = {}
    all_market_ids = set()
    
    for strat_key, strat_name in strategy_names.items():
        filepath = os.path.join(base_dir, f"portfolio_{strat_key}.json")
        
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
        html = generate_empty_dashboard()
        write_dashboard_files(base_dir, html)
        return
    
    print(f"[INFO] Loaded {len(portfolios)} portfolios")
    
    market_data = fetch_market_data(list(all_market_ids))
    
    html = generate_html(portfolios, market_data)
    
    write_dashboard_files(base_dir, html)
    
    print(f"[INFO] Dashboard generated: {os.path.join(base_dir, 'dashboard.html')}")


def write_dashboard_files(base_dir: str, html: str) -> None:
    """Write dashboard HTML to both dashboard.html and index.html."""
    dashboard_path = os.path.join(base_dir, "dashboard.html")
    index_path = os.path.join(base_dir, "index.html")

    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html)

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)


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
    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    
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
        
        # Open positions table with FULL columns
        if positions:
            table_id = f"table-{strat_key}"
            positions_html += f"""
            <div class="section" data-section="{strat_key}">
                <h3 class="section-header" onclick="toggleSection('{strat_key}')">
                    <span class="toggle-icon">▶</span> {name} - Open Positions ({len(positions)})
                </h3>
                <div class="section-content">
                <input type="text" class="search-box" placeholder="Filter positions..." onkeyup="filterTable('{table_id}', this.value)">
                <div class="table-wrapper">
                <table id="{table_id}" class="sortable">
                    <thead>
                        <tr>
                            <th data-sort="string">Market</th>
                            <th data-sort="string">Side</th>
                            <th data-sort="number">Entry YES</th>
                            <th data-sort="number">Current YES</th>
                            <th data-sort="number">P&L</th>
                            <th data-sort="number">Size</th>
                            <th data-sort="string">Cluster</th>
                            <th data-sort="string">Entry Date</th>
                            <th data-sort="string">Expected Close</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for pos in sorted(positions, key=lambda x: x.get("entry_date", ""), reverse=True):
                market_id = pos.get("market_id")
                mkt = market_data.get(market_id, {})
                
                entry_price = pos.get("entry_price", 0)
                shares = pos.get("shares", 0)
                size_usd = pos.get("size_usd", 0)
                bet_side = pos.get("bet_side", "NO")
                entry_date = pos.get("entry_date", "")[:10] if pos.get("entry_date") else "-"
                expected_close = pos.get("expected_close", "")[:10] if pos.get("expected_close") else "-"
                
                # Entry YES price
                if bet_side == "NO":
                    entry_yes = 1 - entry_price
                else:
                    entry_yes = entry_price
                
                current_yes = mkt.get("price_yes")
                if current_yes is not None:
                    if bet_side == "NO":
                        current_no = 1 - current_yes
                        unrealized = (current_no - entry_price) * shares
                    else:
                        unrealized = (current_yes - entry_price) * shares
                    
                    current_str = f"{current_yes:.0%}"
                    pnl_str = f"${unrealized:+.0f}"
                    pnl_cls = "positive" if unrealized > 0 else "negative" if unrealized < 0 else ""
                else:
                    current_str = "-"
                    pnl_str = "-"
                    pnl_cls = ""
                    unrealized = 0
                
                slug = mkt.get("slug", "")
                link = f"https://polymarket.com/event/{slug}" if slug else "#"
                
                positions_html += f"""
                        <tr>
                            <td class="market-name"><a href="{link}" target="_blank" title="{pos.get('question', '')}">{pos.get('question', '')[:50]}...</a></td>
                            <td><span class="badge badge-{pos.get('bet_side', 'NO').lower()}">{pos.get('bet_side', 'NO')}</span></td>
                            <td data-value="{entry_yes}">{entry_yes:.0%}</td>
                            <td data-value="{current_yes if current_yes else 0}">{current_str}</td>
                            <td data-value="{unrealized}" class="{pnl_cls}">{pnl_str}</td>
                            <td data-value="{size_usd}">${size_usd:.0f}</td>
                            <td><span class="tag tag-{pos.get('cluster', 'other')}">{pos.get('cluster', 'other')}</span></td>
                            <td data-value="{entry_date}">{entry_date}</td>
                            <td data-value="{expected_close}">{expected_close}</td>
                        </tr>
                """
            
            positions_html += """
                    </tbody>
                </table>
                </div>
                </div>
            </div>
            """
        
        # Closed trades table
        if closed:
            closed_table_id = f"closed-{strat_key}"
            closed_html += f"""
            <div class="section collapsed" data-section="{closed_table_id}">
                <h3 class="section-header" onclick="toggleSection('{closed_table_id}')">
                    <span class="toggle-icon">▶</span> {name} - Closed Trades ({len(closed)})
                </h3>
                <div class="section-content">
                <div class="table-wrapper">
                <table class="sortable">
                    <thead>
                        <tr>
                            <th data-sort="string">Market</th>
                            <th data-sort="string">Side</th>
                            <th data-sort="string">Result</th>
                            <th data-sort="number">P&L</th>
                            <th data-sort="number">Entry YES</th>
                            <th data-sort="string">Entry Date</th>
                            <th data-sort="string">Close Date</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for trade in sorted(closed, key=lambda x: x.get("close_date", ""), reverse=True):
                result = trade.get("resolution", "")
                pnl_trade = trade.get("pnl", 0)
                result_class = "win" if result == "win" else "lose"
                pnl_class = "positive" if pnl_trade > 0 else "negative"
                
                # Entry YES price
                entry_price = trade.get("entry_price", 0)
                bet_side = trade.get("bet_side", "NO")
                if bet_side == "NO":
                    entry_yes = 1 - entry_price
                else:
                    entry_yes = entry_price
                
                entry_date = trade.get("entry_date", "")[:10] if trade.get("entry_date") else "-"
                close_date = trade.get("close_date", "")[:10] if trade.get("close_date") else "-"
                
                market_id = trade.get("market_id")
                mkt = market_data.get(market_id, {})
                slug = mkt.get("slug", "")
                link = f"https://polymarket.com/event/{slug}" if slug else "#"
                
                closed_html += f"""
                        <tr>
                            <td class="market-name"><a href="{link}" target="_blank" title="{trade.get('question', '')}">{trade.get("question", "")[:50]}...</a></td>
                            <td><span class="badge badge-{trade.get('bet_side', 'NO').lower()}">{trade.get("bet_side", "NO")}</span></td>
                            <td><span class="badge badge-{result_class}">{"✅ WIN" if result == "win" else "❌ LOSS"}</span></td>
                            <td data-value="{pnl_trade}" class="{pnl_class}">${pnl_trade:+.2f}</td>
                            <td data-value="{entry_yes}">{entry_yes:.0%}</td>
                            <td data-value="{entry_date}">{entry_date}</td>
                            <td data-value="{close_date}">{close_date}</td>
                        </tr>
                """
            
            closed_html += """
                    </tbody>
                </table>
                </div>
                </div>
            </div>
            """
    
    # Full HTML with sortable tables
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Polymarket Bot - Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <style>
        :root {{
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-card: #252540;
            --text-primary: #e0e0e0;
            --text-secondary: #888;
            --accent: #00d4ff;
            --positive: #00ff88;
            --negative: #ff4466;
            --border: #2a2a4a;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            background: var(--bg-primary); 
            color: var(--text-primary); 
            padding: 20px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1600px; margin: 0 auto; }}
        h1 {{ color: var(--accent); margin-bottom: 5px; }}
        h2 {{ color: var(--accent); margin: 40px 0 20px 0; }}
        .subtitle {{ color: var(--text-secondary); margin-bottom: 30px; }}
        
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ 
            background: var(--bg-secondary); 
            border-radius: 12px; 
            padding: 20px; 
            border: 1px solid var(--border);
        }}
        .card-positive {{ border-left: 4px solid var(--positive); }}
        .card-negative {{ border-left: 4px solid var(--negative); }}
        .card h2 {{ margin: 0 0 5px 0; font-size: 1.1em; color: #fff; }}
        .strategy-desc {{ color: var(--text-secondary); font-size: 0.85em; margin: 0 0 15px 0; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 15px; }}
        .stat {{ text-align: center; }}
        .stat-value {{ display: block; font-size: 1.3em; font-weight: 600; }}
        .stat-label {{ font-size: 0.75em; color: var(--text-secondary); }}
        
        .positive {{ color: var(--positive); }}
        .negative {{ color: var(--negative); }}
        .win {{ color: var(--positive); }}
        .lose {{ color: var(--negative); }}
        
        .exposure-bar {{ background: var(--border); height: 6px; border-radius: 3px; margin: 10px 0 5px 0; overflow: hidden; }}
        .exposure-fill {{ background: var(--accent); height: 100%; border-radius: 3px; }}
        .exposure-label {{ font-size: 0.75em; color: var(--text-secondary); }}
        
        .cluster-tags {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 5px; }}
        .tag {{ padding: 2px 8px; border-radius: 4px; font-size: 0.7em; background: var(--border); }}
        .tag-mideast {{ background: #3d3529; color: #ffcc80; }}
        .tag-eastern_europe {{ background: #2a3d2a; color: #a5d6a7; }}
        .tag-china {{ background: #3d2929; color: #ef9a9a; }}
        .tag-korea {{ background: #29353d; color: #81d4fa; }}
        .tag-latam {{ background: #3d2940; color: #ce93d8; }}
        .tag-other {{ background: var(--border); color: var(--text-secondary); }}
        
        .section {{ margin-bottom: 20px; }}
        .section-header {{ 
            cursor: pointer; 
            padding: 12px 15px; 
            background: var(--bg-secondary); 
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-header:hover {{ background: var(--bg-card); }}
        .toggle-icon {{ font-size: 0.7em; transition: transform 0.2s; }}
        .section:not(.collapsed) .toggle-icon {{ transform: rotate(90deg); }}
        .section.collapsed .section-content {{ display: none; }}
        .section-content {{ padding: 15px 0; }}
        
        .search-box {{ 
            padding: 8px 12px; 
            border: 1px solid var(--border); 
            border-radius: 6px; 
            background: var(--bg-card); 
            color: var(--text-primary);
            margin-bottom: 10px;
            width: 300px;
        }}
        
        .table-wrapper {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{ 
            background: var(--bg-secondary); 
            font-weight: 500; 
            cursor: pointer; 
            user-select: none;
            white-space: nowrap;
        }}
        th:hover {{ background: #303050; }}
        th.sort-asc::after {{ content: " ▲"; font-size: 0.7em; }}
        th.sort-desc::after {{ content: " ▼"; font-size: 0.7em; }}
        
        .market-name {{ max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .market-name a {{ color: var(--accent); text-decoration: none; }}
        .market-name a:hover {{ text-decoration: underline; }}
        
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 0.7em; font-weight: 500; }}
        .badge-no {{ background: #3d2929; color: #ff8a80; }}
        .badge-yes {{ background: #2a3d29; color: #b9f6ca; }}
        .badge-win {{ background: #2a3d29; color: #b9f6ca; }}
        .badge-lose {{ background: #3d2929; color: #ff8a80; }}
        
        tr:hover {{ background: rgba(255,255,255,0.02); }}
        
        @media (max-width: 768px) {{
            .cards {{ grid-template-columns: 1fr; }}
            table {{ font-size: 0.7em; }}
            .market-name {{ max-width: 150px; }}
            .search-box {{ width: 100%; }}
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
        
        <h2>📈 Open Positions</h2>
        {positions_html if positions_html else '<p style="color: #888;">No open positions</p>'}
        
        <h2>📊 Closed Trades</h2>
        {closed_html if closed_html else '<p style="color: #888;">No closed trades yet</p>'}
    </div>
    
    <script>
        // Toggle sections
        function toggleSection(sectionId) {{
            const section = document.querySelector(`[data-section="${{sectionId}}"]`);
            if (section) section.classList.toggle('collapsed');
        }}
        
        // Filter table
        function filterTable(tableId, query) {{
            const table = document.getElementById(tableId);
            if (!table) return;
            
            const rows = table.querySelectorAll('tbody tr');
            const lowerQuery = query.toLowerCase();
            
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(lowerQuery) ? '' : 'none';
            }});
        }}
        
        // Sortable tables
        document.querySelectorAll('th[data-sort]').forEach(th => {{
            th.addEventListener('click', function() {{
                const table = this.closest('table');
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                const colIndex = Array.from(this.parentNode.children).indexOf(this);
                const sortType = this.dataset.sort;
                
                // Toggle direction
                const isAsc = this.classList.contains('sort-asc');
                table.querySelectorAll('th').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
                this.classList.add(isAsc ? 'sort-desc' : 'sort-asc');
                
                rows.sort((a, b) => {{
                    let aVal = a.children[colIndex]?.dataset.value || a.children[colIndex]?.textContent || '';
                    let bVal = b.children[colIndex]?.dataset.value || b.children[colIndex]?.textContent || '';
                    
                    if (sortType === 'number') {{
                        aVal = parseFloat(aVal) || 0;
                        bVal = parseFloat(bVal) || 0;
                    }}
                    
                    if (aVal < bVal) return isAsc ? 1 : -1;
                    if (aVal > bVal) return isAsc ? -1 : 1;
                    return 0;
                }});
                
                rows.forEach(row => tbody.appendChild(row));
            }});
        }});
    </script>
</body>
</html>
"""
    return html


if __name__ == "__main__":
    generate_dashboard()
