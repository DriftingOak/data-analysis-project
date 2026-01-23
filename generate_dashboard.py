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

def fetch_market_data(market_ids: List[str]) -> Dict[str, dict]:
    """Fetch current data for a list of market IDs."""
    markets = {}
    
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
    
    portfolios = {}
    strategy_names = {
        "conservative": "🛡️ Conservative",
        "balanced": "⚖️ Balanced", 
        "aggressive": "🔥 Aggressive",
        "volume_sweet": "📊 Volume Sweet Spot",
    }
    
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
                all_market_ids.add(pos.get("market_id"))
            for pos in data.get("closed_trades", []):
                all_market_ids.add(pos.get("market_id"))
    
    if not portfolios:
        print("[WARN] No portfolio files found")
        return
    
    market_data = fetch_market_data(list(all_market_ids))
    
    html = generate_html(portfolios, market_data)
    
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"[INFO] Dashboard generated: dashboard.html")

def generate_html(portfolios: Dict, market_data: Dict[str, dict]) -> str:
    """Generate the HTML content."""
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Strategy descriptions
    strategy_desc = {
        "conservative": "Bet NO on YES 10-25%",
        "balanced": "Bet NO on YES 20-60%",
        "aggressive": "Bet NO on YES 30-60%",
        "volume_sweet": "Bet NO on YES 20-60%, Vol $15k-100k",
    }
    
    cards_html = ""
    positions_html = ""
    closed_html = ""
    
    for strat_key, strat_info in portfolios.items():
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
        
        # Card colors - FIXED: check actual values
        total_pnl_display = pnl + unrealized_pnl
        if total_pnl_display > 0:
            card_class = "card-positive"
        elif total_pnl_display < 0:
            card_class = "card-negative"
        else:
            card_class = ""
        
        pnl_class = "positive" if pnl > 0 else "negative" if pnl < 0 else ""
        unrealized_class = "positive" if unrealized_pnl > 0 else "negative" if unrealized_pnl < 0 else ""
        
        cards_html += f"""
        <div class="card {card_class}">
            <h2>{name}</h2>
            <p class="strategy-desc">{strategy_desc.get(strat_key, "")}</p>
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
        
        # Open positions table
        if positions:
            table_id = f"table-{strat_key}"
            
            # Get unique clusters for this strategy
            clusters = sorted(set(p.get("cluster", "other") for p in positions))
            cluster_buttons = "".join(f'<button class="filter-btn" data-cluster="{c}" onclick="filterCluster(\'{table_id}\', \'{c}\', this)">{c}</button>' for c in clusters)
            
            positions_html += f"""
            <div class="section collapsed" data-section="{strat_key}">
                <h3 class="section-header" onclick="toggleSection('{strat_key}')">
                    <span class="toggle-icon">▶</span> {name} - Open Positions ({len(positions)})
                </h3>
                <div class="section-content">
                    <div class="table-controls">
                        <input type="text" class="search-box" placeholder="Search markets..." onkeyup="filterTable('{table_id}', this.value)">
                        <div class="cluster-filters">
                            <button class="filter-btn active" data-cluster="all" onclick="filterCluster('{table_id}', 'all', this)">All</button>
                            {cluster_buttons}
                        </div>
                    </div>
                    <div class="table-wrapper">
                    <table id="{table_id}" class="sortable">
                        <thead>
                            <tr>
                                <th data-sort="string">Market</th>
                                <th data-sort="string">Side</th>
                                <th data-sort="number">YES Entry</th>
                                <th data-sort="number">YES Current</th>
                                <th data-sort="number">Δ</th>
                                <th data-sort="number">P&L</th>
                                <th data-sort="number">Size</th>
                                <th data-sort="string">Cluster</th>
                                <th data-sort="string">Entry Date</th>
                                <th data-sort="string">End Date</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            for pos in sorted(positions, key=lambda x: x.get("entry_date", ""), reverse=True):
                market_id = pos.get("market_id")
                entry_no_price = pos.get("entry_price", 0)
                entry_yes = 1 - entry_no_price  # Convert to YES
                bet_side = pos.get("bet_side", "NO")
                shares = pos.get("shares", 0)
                
                mkt = market_data.get(market_id, {})
                slug = mkt.get("slug", "")
                current_yes = mkt.get("price_yes")
                
                # Build Polymarket link
                if slug:
                    link = f"https://polymarket.com/event/{slug}"
                else:
                    link = f"https://polymarket.com/markets/{market_id}"
                
                if current_yes is not None:
                    delta_yes = current_yes - entry_yes
                    
                    # P&L calculation (based on NO position)
                    if bet_side == "NO":
                        delta_pnl = ((1 - current_yes) - entry_no_price) * shares
                    else:
                        delta_pnl = (current_yes - entry_no_price) * shares
                    
                    # Color: for NO bet, we PROFIT when YES goes DOWN
                    if bet_side == "NO":
                        delta_class = "positive" if delta_yes < 0 else "negative" if delta_yes > 0 else ""
                    else:
                        delta_class = "positive" if delta_yes > 0 else "negative" if delta_yes < 0 else ""
                    
                    pnl_class = "positive" if delta_pnl > 0 else "negative" if delta_pnl < 0 else ""
                    
                    current_str = f"{current_yes:.0%}"
                    delta_str = f'{delta_yes:+.0%}'
                    pnl_str = f'${delta_pnl:+.0f}'
                    
                    # Data attributes for sorting
                    current_data = current_yes
                    delta_data = delta_yes
                    pnl_data = delta_pnl
                else:
                    current_str = "—"
                    delta_str = "—"
                    pnl_str = "—"
                    delta_class = ""
                    pnl_class = ""
                    current_data = 0
                    delta_data = 0
                    pnl_data = 0
                
                positions_html += f"""
                        <tr>
                            <td class="market-name"><a href="{link}" target="_blank" title="{pos.get('question', '')}">{pos.get("question", "")[:50]}...</a></td>
                            <td><span class="badge badge-{pos.get('bet_side', '').lower()}">{pos.get("bet_side", "")}</span></td>
                            <td data-value="{entry_yes}">{entry_yes:.0%}</td>
                            <td data-value="{current_data}">{current_str}</td>
                            <td data-value="{delta_data}" class="{delta_class}">{delta_str}</td>
                            <td data-value="{pnl_data}" class="{pnl_class}">{pnl_str}</td>
                            <td data-value="{pos.get('size_usd', 0)}">${pos.get("size_usd", 0):.0f}</td>
                            <td><span class="tag tag-{pos.get('cluster', 'other')}">{pos.get("cluster", "")}</span></td>
                            <td>{pos.get("entry_date", "")[:10]}</td>
                            <td>{pos.get("expected_close", "")[:10]}</td>
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
            table_id = f"table-closed-{strat_key}"
            closed_html += f"""
            <div class="section collapsed" data-section="closed-{strat_key}">
                <h3 class="section-header" onclick="toggleSection('closed-{strat_key}')">
                    <span class="toggle-icon">▶</span> {name} - Closed Trades ({len(closed)} total)
                </h3>
                <div class="section-content">
                <div class="table-wrapper">
                <table id="{table_id}" class="sortable">
                    <thead>
                        <tr>
                            <th data-sort="string">Market</th>
                            <th data-sort="string">Side</th>
                            <th data-sort="string">Result</th>
                            <th data-sort="number">P&L</th>
                            <th data-sort="number">YES Entry</th>
                            <th data-sort="string">Closed</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for trade in sorted(closed, key=lambda x: x.get("close_date", ""), reverse=True):
                result = trade.get("resolution", "")
                pnl_trade = trade.get("pnl", 0)
                result_class = "win" if result == "win" else "lose"
                pnl_class = "positive" if pnl_trade > 0 else "negative" if pnl_trade < 0 else ""
                
                market_id = trade.get("market_id")
                mkt = market_data.get(market_id, {})
                slug = mkt.get("slug", "")
                
                entry_no_price = trade.get("entry_price", 0)
                entry_yes = 1 - entry_no_price
                
                if slug:
                    link = f"https://polymarket.com/event/{slug}"
                else:
                    link = f"https://polymarket.com/markets/{market_id}"
                
                closed_html += f"""
                        <tr>
                            <td class="market-name"><a href="{link}" target="_blank" title="{trade.get('question', '')}">{trade.get("question", "")[:50]}...</a></td>
                            <td><span class="badge badge-{trade.get('bet_side', '').lower()}">{trade.get("bet_side", "")}</span></td>
                            <td><span class="badge badge-{result_class}">{"✅ WIN" if result == "win" else "❌ LOSS"}</span></td>
                            <td data-value="{pnl_trade}" class="{pnl_class}">${pnl_trade:+.2f}</td>
                            <td data-value="{entry_yes}">{entry_yes:.0%}</td>
                            <td>{trade.get("close_date", "")[:10]}</td>
                        </tr>
                """
            closed_html += """
                    </tbody>
                </table>
                </div>
                </div>
            </div>
            """
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
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
            margin-bottom: 5px;
            color: var(--text-primary);
        }}
        
        .strategy-desc {{
            font-size: 0.75rem;
            color: var(--accent);
            margin-bottom: 15px;
            font-style: italic;
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
        
        .positive {{ color: var(--positive) !important; }}
        .negative {{ color: var(--negative) !important; }}
        
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
        
        .section-header {{
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            user-select: none;
        }}
        
        .section-header:hover {{
            color: var(--accent);
        }}
        
        .toggle-icon {{
            font-size: 0.8rem;
            transition: transform 0.2s;
        }}
        
        .section:not(.collapsed) .toggle-icon {{
            transform: rotate(90deg);
        }}
        
        .section.collapsed .section-content {{
            display: none;
        }}
        
        .section-content {{
            margin-top: 15px;
        }}
        
        .table-controls {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 15px;
            align-items: center;
        }}
        
        .search-box {{
            padding: 8px 12px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 0.85rem;
            min-width: 200px;
        }}
        
        .search-box:focus {{
            outline: none;
            border-color: var(--accent);
        }}
        
        .cluster-filters {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }}
        
        .filter-btn {{
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid var(--border);
            background: var(--bg-primary);
            color: var(--text-secondary);
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .filter-btn:hover {{
            border-color: var(--accent);
            color: var(--text-primary);
        }}
        
        .filter-btn.active {{
            background: var(--accent);
            border-color: var(--accent);
            color: white;
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
            cursor: pointer;
            user-select: none;
        }}
        
        th:hover {{
            color: var(--text-primary);
            background: var(--bg-card);
        }}
        
        th.sort-asc::after {{
            content: " ▲";
            font-size: 0.7rem;
        }}
        
        th.sort-desc::after {{
            content: " ▼";
            font-size: 0.7rem;
        }}
        
        .market-name {{
            max-width: 280px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .market-name a {{
            color: var(--text-primary);
            text-decoration: none;
        }}
        
        .market-name a:hover {{
            color: var(--accent);
            text-decoration: underline;
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
            <h1>📈 Dashboard</h1>
            <p class="subtitle">Last updated: {now} UTC</p>
        </header>
        
        <div class="cards">
            {cards_html}
        </div>
        
        {closed_html}
        
        {positions_html}
    </div>
    
    <script>
        // Toggle sections
        function toggleSection(sectionId) {{
            const section = document.querySelector(`[data-section="${{sectionId}}"]`);
            if (section) {{
                section.classList.toggle('collapsed');
            }}
        }}
        
        // Search filter
        function filterTable(tableId, query) {{
            const table = document.getElementById(tableId);
            if (!table) return;
            
            const rows = table.querySelectorAll('tbody tr');
            const lowerQuery = query.toLowerCase();
            
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                const matchesSearch = text.includes(lowerQuery);
                const currentDisplay = row.style.display;
                
                // Check if row is also filtered by cluster
                const isClusterHidden = row.dataset.clusterHidden === 'true';
                
                if (matchesSearch && !isClusterHidden) {{
                    row.style.display = '';
                }} else {{
                    row.style.display = 'none';
                }}
                
                row.dataset.searchHidden = !matchesSearch;
            }});
        }}
        
        // Cluster filter
        function filterCluster(tableId, cluster, btn) {{
            const table = document.getElementById(tableId);
            if (!table) return;
            
            // Update active button
            const buttons = btn.parentElement.querySelectorAll('.filter-btn');
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(row => {{
                const rowCluster = row.querySelector('.tag')?.textContent.trim() || '';
                const matchesCluster = cluster === 'all' || rowCluster === cluster;
                const isSearchHidden = row.dataset.searchHidden === 'true';
                
                if (matchesCluster && !isSearchHidden) {{
                    row.style.display = '';
                }} else {{
                    row.style.display = 'none';
                }}
                
                row.dataset.clusterHidden = !matchesCluster;
            }});
        }}
        
        // Sortable tables
        document.querySelectorAll('table.sortable').forEach(table => {{
            const headers = table.querySelectorAll('th[data-sort]');
            
            headers.forEach((header, index) => {{
                header.addEventListener('click', () => {{
                    const type = header.dataset.sort;
                    const tbody = table.querySelector('tbody');
                    const rows = Array.from(tbody.querySelectorAll('tr'));
                    
                    // Determine sort direction
                    const isAsc = header.classList.contains('sort-asc');
                    
                    // Remove sort classes from all headers
                    headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
                    
                    // Add new sort class
                    header.classList.add(isAsc ? 'sort-desc' : 'sort-asc');
                    
                    // Sort rows
                    rows.sort((a, b) => {{
                        const aCell = a.cells[index];
                        const bCell = b.cells[index];
                        
                        let aVal, bVal;
                        
                        if (type === 'number') {{
                            aVal = parseFloat(aCell.dataset.value) || 0;
                            bVal = parseFloat(bCell.dataset.value) || 0;
                        }} else {{
                            aVal = aCell.textContent.trim().toLowerCase();
                            bVal = bCell.textContent.trim().toLowerCase();
                        }}
                        
                        if (aVal < bVal) return isAsc ? 1 : -1;
                        if (aVal > bVal) return isAsc ? -1 : 1;
                        return 0;
                    }});
                    
                    // Re-append sorted rows
                    rows.forEach(row => tbody.appendChild(row));
                }});
            }});
        }});
    </script>
</body>
</html>
"""
    
    return html


if __name__ == "__main__":
    generate_dashboard()
