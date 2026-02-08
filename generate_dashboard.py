#!/usr/bin/env python3
"""
POLYMARKET BOT - Dashboard Generator (v2)
==========================================
Generates a single-page HTML dashboard from portfolio JSON files.

Optimized for 24 strategies:
- Compact comparison table (sortable)
- P&L history chart over time
- Expandable per-strategy position details
- Batch market data fetching

Usage:
    python generate_dashboard.py
"""

import json
import os
import time
import glob
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

# =============================================================================
# CONFIG
# =============================================================================

GAMMA_API = "https://gamma-api.polymarket.com"
HISTORY_FILE = "pnl_history.json"


def compact_history(history: list) -> list:
    """Keep all points from last 7 days, then 1 per day for older data.
    
    This way history lasts months/years without bloating the JSON.
    """
    if len(history) < 10:
        return history

    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT")

    recent = []
    older = {}  # date_str -> last entry for that day

    for entry in history:
        ts = entry.get("ts", "")
        if ts >= cutoff:
            recent.append(entry)
        else:
            day = ts[:10]  # "YYYY-MM-DD"
            older[day] = entry  # keep last entry per day

    compacted = sorted(older.values(), key=lambda e: e["ts"]) + recent
    return compacted


# =============================================================================
# DATA LOADING
# =============================================================================

def discover_portfolios() -> Dict[str, dict]:
    """Find all portfolio_*.json files and load them."""
    portfolios = {}
    for filepath in sorted(glob.glob("portfolio_*.json")):
        strat_key = filepath.replace("portfolio_", "").replace(".json", "")
        try:
            with open(filepath) as f:
                data = json.load(f)
            portfolios[strat_key] = data
        except Exception as e:
            print(f"[WARN] Failed to load {filepath}: {e}")
    return portfolios


def get_strategy_meta(strat_key: str) -> dict:
    """Get strategy metadata (tier, description) from strategies.py if available."""
    try:
        import strategies as strat_config
        if strat_key in strat_config.STRATEGIES:
            s = strat_config.STRATEGIES[strat_key]
            return {
                "name": s.get("name", strat_key),
                "description": s.get("description", ""),
                "bet_side": s.get("bet_side", "NO"),
                "bankroll": s.get("bankroll", 5000),
            }
    except ImportError:
        pass
    # Fallback
    return {"name": strat_key, "description": "", "bet_side": "NO", "bankroll": 5000}


def collect_all_market_ids(portfolios: Dict[str, dict]) -> set:
    """Collect unique market IDs across all portfolios."""
    ids = set()
    for data in portfolios.values():
        for pos in data.get("positions", []):
            mid = pos.get("market_id")
            if mid:
                ids.add(mid)
        for pos in data.get("closed_trades", []):
            mid = pos.get("market_id")
            if mid:
                ids.add(mid)
    return ids


def batch_fetch_markets(market_ids: set) -> Dict[str, dict]:
    """Fetch market data in batch with rate limiting."""
    markets = {}
    ids_list = list(market_ids)
    print(f"[INFO] Fetching {len(ids_list)} unique markets...")

    for i, mid in enumerate(ids_list):
        try:
            resp = requests.get(f"{GAMMA_API}/markets/{mid}", timeout=10)
            if resp.status_code != 200:
                continue
            m = resp.json()

            prices_raw = m.get("outcomePrices", "")
            if isinstance(prices_raw, str) and prices_raw:
                price_list = json.loads(prices_raw)
            else:
                price_list = prices_raw or []

            price_yes = float(price_list[0]) if price_list else None

            markets[mid] = {
                "price_yes": price_yes,
                "slug": m.get("slug", ""),
                "question": m.get("question", ""),
                "closed": m.get("closed", False),
            }
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(ids_list)}...")
            time.sleep(0.02)
        except Exception:
            pass

    print(f"[INFO] Got data for {len(markets)}/{len(ids_list)} markets")
    return markets


# =============================================================================
# P&L HISTORY
# =============================================================================

def update_pnl_history(portfolios: Dict[str, dict], market_data: Dict[str, dict]):
    """Append current P&L snapshot to history file."""
    try:
        with open(HISTORY_FILE) as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"ts": now_iso, "strategies": {}}

    for strat_key, data in portfolios.items():
        realized = data.get("total_pnl", 0)
        # Calculate unrealized
        unrealized = 0
        for pos in data.get("positions", []):
            if pos.get("status") != "open":
                continue
            mkt = market_data.get(pos.get("market_id"), {})
            cy = mkt.get("price_yes")
            if cy is not None:
                ep = pos.get("entry_price", 0)
                sh = pos.get("shares", 0)
                bs = pos.get("bet_side", "NO")
                if bs == "NO":
                    unrealized += ((1 - cy) - ep) * sh
                else:
                    unrealized += (cy - ep) * sh

        entry["strategies"][strat_key] = {
            "realized": round(realized, 2),
            "unrealized": round(unrealized, 2),
            "total": round(realized + unrealized, 2),
            "open": len([p for p in data.get("positions", []) if p.get("status") == "open"]),
            "wins": data.get("wins", 0),
            "losses": data.get("losses", 0),
        }

    history.append(entry)
    history = compact_history(history)

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)
    print(f"[INFO] P&L history updated ({len(history)} points)")
    return history


# =============================================================================
# STRATEGY STATS
# =============================================================================

def compute_strategy_stats(
    strat_key: str, data: dict, market_data: Dict[str, dict]
) -> dict:
    """Compute all stats for one strategy."""
    meta = get_strategy_meta(strat_key)
    initial = data.get("bankroll_initial", 5000)
    current = data.get("bankroll_current", initial)
    realized = data.get("total_pnl", 0)
    wins = data.get("wins", 0)
    losses = data.get("losses", 0)
    total_trades = data.get("total_trades", 0)

    positions = [p for p in data.get("positions", []) if p.get("status") == "open"]
    closed = data.get("closed_trades", [])

    # Unrealized P&L
    unrealized = 0
    exposure_total = 0
    exposure_by_cluster = {}
    for pos in positions:
        size = pos.get("size_usd", 0)
        cluster = pos.get("cluster", "other")
        exposure_total += size
        exposure_by_cluster[cluster] = exposure_by_cluster.get(cluster, 0) + size

        mkt = market_data.get(pos.get("market_id"), {})
        cy = mkt.get("price_yes")
        if cy is not None:
            ep = pos.get("entry_price", 0)
            sh = pos.get("shares", 0)
            bs = pos.get("bet_side", "NO")
            if bs == "NO":
                unrealized += ((1 - cy) - ep) * sh
            else:
                unrealized += (cy - ep) * sh

    total_pnl = realized + unrealized
    roi = (realized / initial * 100) if initial > 0 else 0
    total_roi = (total_pnl / initial * 100) if initial > 0 else 0
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

    return {
        "key": strat_key,
        "name": meta["name"],
        "description": meta["description"],
        "initial": initial,
        "current": current,
        "realized": realized,
        "unrealized": unrealized,
        "total_pnl": total_pnl,
        "roi": roi,
        "total_roi": total_roi,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "open_count": len(positions),
        "closed_count": len(closed),
        "exposure": exposure_total,
        "exposure_pct": (exposure_total / current * 100) if current > 0 else 0,
        "clusters": exposure_by_cluster,
        "positions": positions,
        "closed_trades": closed,
    }


# =============================================================================
# TIER CLASSIFICATION
# =============================================================================

def get_tier(key: str) -> str:
    """Classify strategy into tier for grouping."""
    if key in ("conservative", "balanced", "aggressive", "volume_sweet"):
        return "base"
    for t in ("t1_", "t2_", "t3_", "t4_", "t5_"):
        if key.startswith(t):
            return t.rstrip("_")
    return "other"


def tier_label(tier: str) -> str:
    labels = {
        "base": "Base (legacy)",
        "t1": "Tier 1 — Controls",
        "t2": "Tier 2 — Volume Hypothesis",
        "t3": "Tier 3 — Multi-Bucket",
        "t4": "Tier 4 — Cash-Constrained",
        "t5": "Tier 5 — Deployable",
        "other": "Other",
    }
    return labels.get(tier, tier)


# =============================================================================
# HTML GENERATION
# =============================================================================

def generate_html(
    all_stats: List[dict],
    market_data: Dict[str, dict],
    history: list,
) -> str:
    """Generate the full HTML dashboard."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Aggregate stats ──
    total_realized = sum(s["realized"] for s in all_stats)
    total_unrealized = sum(s["unrealized"] for s in all_stats)
    total_open = sum(s["open_count"] for s in all_stats)
    total_closed = sum(s["closed_count"] for s in all_stats)
    total_wins = sum(s["wins"] for s in all_stats)
    total_losses = sum(s["losses"] for s in all_stats)

    # ── Comparison table rows ──
    comparison_rows = ""
    for s in sorted(all_stats, key=lambda x: x["total_pnl"], reverse=True):
        tier = get_tier(s["key"])
        pnl_cls = "pos" if s["total_pnl"] >= 0 else "neg"
        real_cls = "pos" if s["realized"] >= 0 else "neg"
        wr_cls = "pos" if s["win_rate"] >= 60 else ("neg" if s["win_rate"] < 45 and s["wins"] + s["losses"] > 0 else "")
        comparison_rows += f"""<tr data-tier="{tier}" onclick="toggleDetail('{s["key"]}')">
<td class="strat-name"><span class="tier-dot tier-{tier}"></span>{s["name"]}</td>
<td class="{real_cls}" data-v="{s['realized']:.1f}">${s["realized"]:+,.0f}</td>
<td class="{pnl_cls}" data-v="{s['total_pnl']:.1f}">${s["total_pnl"]:+,.0f}</td>
<td class="{pnl_cls}" data-v="{s['total_roi']:.1f}">{s["total_roi"]:+.1f}%</td>
<td class="{wr_cls}" data-v="{s['win_rate']:.1f}">{s["win_rate"]:.0f}%</td>
<td data-v="{s['wins']+s['losses']}">{s["wins"]}W/{s["losses"]}L</td>
<td data-v="{s['open_count']}">{s["open_count"]}</td>
<td data-v="{s['exposure_pct']:.0f}">{s["exposure_pct"]:.0f}%</td>
</tr>\n"""

    # ── Position detail panels (hidden by default) ──
    detail_panels = ""
    for s in all_stats:
        # Open positions
        open_rows = ""
        for pos in sorted(s["positions"], key=lambda p: p.get("entry_date", ""), reverse=True):
            mid = pos.get("market_id", "")
            mkt = market_data.get(mid, {})
            question = (pos.get("question") or mkt.get("question", mid))[:65]
            slug = mkt.get("slug", "")
            link = f"https://polymarket.com/event/{slug}" if slug else "#"
            ep = pos.get("entry_price", 0)
            sh = pos.get("shares", 0)
            bs = pos.get("bet_side", "NO")
            size = pos.get("size_usd", 0)
            cluster = pos.get("cluster", "")
            entry_d = (pos.get("entry_date") or "")[:10]
            exp_close = (pos.get("expected_close") or "")[:10]

            cy = mkt.get("price_yes")
            if cy is not None:
                entry_yes = (1 - ep) if bs == "NO" else ep
                if bs == "NO":
                    unr = ((1 - cy) - ep) * sh
                else:
                    unr = (cy - ep) * sh
                cur_str = f"{cy:.0%}"
                pnl_str = f"${unr:+,.0f}"
                pnl_cls = "pos" if unr >= 0 else "neg"
            else:
                entry_yes = (1 - ep) if bs == "NO" else ep
                cur_str = "—"
                pnl_str = "—"
                pnl_cls = ""

            open_rows += f"""<tr>
<td class="q-cell"><a href="{link}" target="_blank">{question}</a></td>
<td><span class="badge badge-{bs.lower()}">{bs}</span></td>
<td>{entry_yes:.0%}</td><td>{cur_str}</td>
<td class="{pnl_cls}">{pnl_str}</td>
<td>${size:.0f}</td><td>{cluster}</td><td>{entry_d}</td><td>{exp_close}</td>
</tr>\n"""

        # Closed trades
        closed_rows = ""
        for pos in sorted(s["closed_trades"], key=lambda p: p.get("close_date") or p.get("entry_date", ""), reverse=True)[:30]:
            question = (pos.get("question") or "")[:65]
            ep = pos.get("entry_price", 0)
            bs = pos.get("bet_side", "NO")
            size = pos.get("size_usd", 0)
            pnl = pos.get("pnl", 0)
            res = pos.get("resolution", "")
            entry_d = (pos.get("entry_date") or "")[:10]
            close_d = (pos.get("close_date") or "")[:10]
            entry_yes = (1 - ep) if bs == "NO" else ep
            res_cls = "pos" if res == "win" else "neg"
            pnl_cls = "pos" if pnl and pnl > 0 else "neg"

            closed_rows += f"""<tr>
<td class="q-cell">{question}</td>
<td><span class="badge badge-{bs.lower()}">{bs}</span></td>
<td>{entry_yes:.0%}</td>
<td class="{res_cls}"><span class="badge badge-{res}">{res}</span></td>
<td class="{pnl_cls}">${pnl:+,.0f}</td>
<td>${size:.0f}</td><td>{entry_d}</td><td>{close_d}</td>
</tr>\n"""

        cluster_tags = " ".join(
            f'<span class="tag">{c}: ${v:.0f}</span>'
            for c, v in sorted(s["clusters"].items(), key=lambda x: -x[1])
        )

        detail_panels += f"""
<div class="detail-panel" id="detail-{s['key']}" style="display:none">
  <div class="detail-header">
    <h3>{s['name']}</h3>
    <p class="desc">{s['description']}</p>
    <div class="detail-meta">
      Bankroll: ${s['current']:,.0f} | Exposure: ${s['exposure']:,.0f} ({s['exposure_pct']:.0f}%)
      {(' | Clusters: ' + cluster_tags) if cluster_tags else ''}
    </div>
  </div>
  <div class="detail-tabs">
    <button class="tab-btn active" onclick="switchTab('{s['key']}','open')">Open ({s['open_count']})</button>
    <button class="tab-btn" onclick="switchTab('{s['key']}','closed')">Closed ({s['closed_count']})</button>
  </div>
  <div class="tab-content" id="tab-{s['key']}-open">
    {f'''<table class="pos-table"><thead><tr>
    <th>Market</th><th>Side</th><th>Entry YES</th><th>Current</th><th>P&L</th><th>Size</th><th>Cluster</th><th>Entry</th><th>Exp. Close</th>
    </tr></thead><tbody>{open_rows}</tbody></table>''' if open_rows else '<p class="empty">No open positions</p>'}
  </div>
  <div class="tab-content" id="tab-{s['key']}-closed" style="display:none">
    {f'''<table class="pos-table"><thead><tr>
    <th>Market</th><th>Side</th><th>Entry YES</th><th>Result</th><th>P&L</th><th>Size</th><th>Entry</th><th>Closed</th>
    </tr></thead><tbody>{closed_rows}</tbody></table>''' if closed_rows else '<p class="empty">No closed trades yet</p>'}
  </div>
</div>\n"""

    # ── History data for chart ──
    history_json = json.dumps(history[-100:]) if history else "[]"

    # ── Tier filter buttons ──
    tiers_present = sorted(set(get_tier(s["key"]) for s in all_stats))
    tier_btns = '<button class="filter-btn active" data-tier="all">All</button>'
    for t in tiers_present:
        tier_btns += f'<button class="filter-btn" data-tier="{t}">{tier_label(t)}</button>'

    agg_pnl_cls = "pos" if (total_realized + total_unrealized) >= 0 else "neg"
    agg_wr = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="360">
<title>Polymarket Geopolitical Bot</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Outfit:wght@300;400;600;700&display=swap');

:root {{
  --bg: #0a0a12;
  --bg2: #12121e;
  --bg3: #1a1a2c;
  --bg-hover: #22223a;
  --border: #2a2a42;
  --text: #c8c8d8;
  --text2: #7878a0;
  --accent: #5ee8b7;
  --accent2: #3db896;
  --pos: #5ee8b7;
  --neg: #f06888;
  --warn: #f0c060;
  --blue: #60a0f0;
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:'Outfit',sans-serif; font-size:14px; }}

.wrap {{ max-width:1440px; margin:0 auto; padding:24px; }}

/* ── Header ── */
header {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:28px; flex-wrap:wrap; gap:12px; }}
header h1 {{ font-size:1.6em; font-weight:700; color:#fff; letter-spacing:-0.02em; }}
header h1 span {{ color:var(--accent); }}
.updated {{ font-size:0.82em; color:var(--text2); }}

/* ── Aggregate bar ── */
.agg {{ display:flex; gap:32px; padding:16px 24px; background:var(--bg2); border:1px solid var(--border); border-radius:10px; margin-bottom:24px; flex-wrap:wrap; }}
.agg-item {{ text-align:center; }}
.agg-val {{ display:block; font-family:'JetBrains Mono',monospace; font-size:1.3em; font-weight:700; }}
.agg-lbl {{ font-size:0.72em; color:var(--text2); text-transform:uppercase; letter-spacing:0.06em; }}

/* ── Tier filters ── */
.filters {{ display:flex; gap:6px; margin-bottom:16px; flex-wrap:wrap; }}
.filter-btn {{
  background:var(--bg2); border:1px solid var(--border); color:var(--text2);
  padding:5px 14px; border-radius:6px; font-size:0.78em; cursor:pointer;
  font-family:'Outfit',sans-serif; transition:all .15s;
}}
.filter-btn:hover {{ border-color:var(--accent); color:var(--text); }}
.filter-btn.active {{ background:var(--accent); color:var(--bg); border-color:var(--accent); font-weight:600; }}

/* ── Comparison table ── */
.comp-wrap {{ overflow-x:auto; margin-bottom:8px; }}
.comp {{ width:100%; border-collapse:collapse; font-size:0.85em; }}
.comp th {{
  text-align:left; padding:8px 10px; color:var(--text2); font-weight:600;
  border-bottom:2px solid var(--border); cursor:pointer; white-space:nowrap;
  font-size:0.78em; text-transform:uppercase; letter-spacing:0.04em;
  user-select:none; position:sticky; top:0; background:var(--bg);
}}
.comp th:hover {{ color:var(--accent); }}
.comp th.sorted-asc::after {{ content:" ▲"; font-size:0.65em; }}
.comp th.sorted-desc::after {{ content:" ▼"; font-size:0.65em; }}
.comp td {{
  padding:7px 10px; border-bottom:1px solid var(--border);
  font-family:'JetBrains Mono',monospace; font-size:0.92em; white-space:nowrap;
}}
.comp tr {{ cursor:pointer; transition:background .1s; }}
.comp tr:hover {{ background:var(--bg-hover); }}
.comp tr.expanded {{ background:var(--bg3); }}
.strat-name {{ font-family:'Outfit',sans-serif; font-weight:600; color:#fff; }}

.tier-dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }}
.tier-base {{ background:#7878a0; }}
.tier-t1 {{ background:#60a0f0; }}
.tier-t2 {{ background:#f0c060; }}
.tier-t3 {{ background:#c080f0; }}
.tier-t4 {{ background:#f08060; }}
.tier-t5 {{ background:#5ee8b7; }}
.tier-other {{ background:#555; }}

.pos {{ color:var(--pos); }}
.neg {{ color:var(--neg); }}

/* ── Chart ── */
.chart-section {{ margin:28px 0; }}
.chart-section h2 {{ font-size:1.1em; margin-bottom:12px; color:#fff; }}
#chart {{ width:100%; height:260px; background:var(--bg2); border:1px solid var(--border); border-radius:10px; }}

/* ── Detail panels ── */
.detail-panel {{
  background:var(--bg2); border:1px solid var(--border); border-radius:10px;
  margin-bottom:6px; overflow:hidden; animation:slideDown .2s ease;
}}
@keyframes slideDown {{ from {{ opacity:0; max-height:0; }} to {{ opacity:1; max-height:2000px; }} }}
.detail-header {{ padding:16px 20px 8px; }}
.detail-header h3 {{ font-size:1em; color:#fff; }}
.desc {{ color:var(--text2); font-size:0.82em; margin:2px 0 6px; }}
.detail-meta {{ font-size:0.78em; color:var(--text2); }}

.detail-tabs {{ padding:0 20px; display:flex; gap:4px; }}
.tab-btn {{
  background:none; border:none; color:var(--text2); padding:8px 16px;
  font-family:'Outfit',sans-serif; font-size:0.82em; cursor:pointer;
  border-bottom:2px solid transparent; transition:all .15s;
}}
.tab-btn:hover {{ color:var(--text); }}
.tab-btn.active {{ color:var(--accent); border-bottom-color:var(--accent); }}

.tab-content {{ padding:0 20px 16px; }}
.pos-table {{ width:100%; border-collapse:collapse; font-size:0.8em; margin-top:8px; }}
.pos-table th {{ text-align:left; padding:6px 8px; color:var(--text2); font-weight:500; font-size:0.82em; border-bottom:1px solid var(--border); }}
.pos-table td {{ padding:5px 8px; border-bottom:1px solid rgba(42,42,66,0.5); font-family:'JetBrains Mono',monospace; font-size:0.9em; }}
.q-cell {{ font-family:'Outfit',sans-serif; max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.q-cell a {{ color:var(--blue); text-decoration:none; }}
.q-cell a:hover {{ text-decoration:underline; }}

.badge {{ padding:2px 7px; border-radius:3px; font-size:0.78em; font-weight:600; }}
.badge-no {{ background:rgba(240,104,136,0.15); color:var(--neg); }}
.badge-yes {{ background:rgba(94,232,183,0.15); color:var(--pos); }}
.badge-win {{ background:rgba(94,232,183,0.15); color:var(--pos); }}
.badge-lose {{ background:rgba(240,104,136,0.15); color:var(--neg); }}

.tag {{ display:inline-block; padding:1px 8px; background:var(--bg3); border-radius:3px; font-size:0.78em; margin:0 3px; }}
.empty {{ color:var(--text2); font-size:0.85em; padding:16px 0; }}

/* ── Responsive ── */
@media (max-width:768px) {{
  .agg {{ gap:16px; }}
  .agg-val {{ font-size:1em; }}
  .comp {{ font-size:0.75em; }}
  .q-cell {{ max-width:160px; }}
}}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1><span>▲</span> Polymarket Geopolitical Bot</h1>
  <span class="updated">{now} · auto-refresh 6min</span>
</header>

<div class="agg">
  <div class="agg-item"><span class="agg-val">{len(all_stats)}</span><span class="agg-lbl">Strategies</span></div>
  <div class="agg-item"><span class="agg-val {agg_pnl_cls}">${total_realized:+,.0f}</span><span class="agg-lbl">Realized P&L</span></div>
  <div class="agg-item"><span class="agg-val {agg_pnl_cls}">${total_unrealized:+,.0f}</span><span class="agg-lbl">Unrealized</span></div>
  <div class="agg-item"><span class="agg-val">{total_open}</span><span class="agg-lbl">Open</span></div>
  <div class="agg-item"><span class="agg-val">{total_closed}</span><span class="agg-lbl">Closed</span></div>
  <div class="agg-item"><span class="agg-val">{agg_wr:.0f}%</span><span class="agg-lbl">Win Rate ({total_wins}W/{total_losses}L)</span></div>
</div>

<div class="chart-section">
  <h2>P&L History</h2>
  <canvas id="chart"></canvas>
</div>

<div class="filters">{tier_btns}</div>

<div class="comp-wrap">
<table class="comp" id="compTable">
<thead><tr>
  <th data-col="0" data-type="str">Strategy</th>
  <th data-col="1" data-type="num">Realized</th>
  <th data-col="2" data-type="num">Total P&L</th>
  <th data-col="3" data-type="num">ROI</th>
  <th data-col="4" data-type="num">Win Rate</th>
  <th data-col="5" data-type="num">W/L</th>
  <th data-col="6" data-type="num">Open</th>
  <th data-col="7" data-type="num">Exposure</th>
</tr></thead>
<tbody>{comparison_rows}</tbody>
</table>
</div>

{detail_panels}

</div>

<script>
// ── P&L Chart (lightweight canvas) ──
const history = {history_json};
function drawChart() {{
  const canvas = document.getElementById('chart');
  if (!canvas || !history.length) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  const W = rect.width, H = rect.height;
  const pad = {{t:20, r:20, b:30, l:60}};
  const cW = W - pad.l - pad.r, cH = H - pad.t - pad.b;

  // Aggregate total P&L per timestamp
  const points = history.map(h => {{
    let total = 0;
    for (const s of Object.values(h.strategies)) total += (s.total || 0);
    return {{ ts: h.ts, val: total }};
  }});

  if (points.length < 2) {{
    ctx.fillStyle = '#7878a0';
    ctx.font = '13px Outfit';
    ctx.fillText('Need more data points...', W/2 - 70, H/2);
    return;
  }}

  const vals = points.map(p => p.val);
  let minV = Math.min(...vals, 0);
  let maxV = Math.max(...vals, 0);
  if (minV === maxV) {{ minV -= 10; maxV += 10; }}
  const rangeV = maxV - minV;

  // Grid
  ctx.strokeStyle = '#2a2a42';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {{
    const y = pad.t + (cH / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
    const v = maxV - (rangeV / 4) * i;
    ctx.fillStyle = '#7878a0'; ctx.font = '11px JetBrains Mono';
    ctx.textAlign = 'right';
    ctx.fillText('$' + v.toFixed(0), pad.l - 8, y + 4);
  }}

  // Zero line
  if (minV < 0 && maxV > 0) {{
    const zeroY = pad.t + ((maxV - 0) / rangeV) * cH;
    ctx.strokeStyle = '#4a4a6a'; ctx.lineWidth = 1; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l, zeroY); ctx.lineTo(W - pad.r, zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }}

  // Line
  ctx.beginPath();
  ctx.strokeStyle = points[points.length-1].val >= 0 ? '#5ee8b7' : '#f06888';
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  for (let i = 0; i < points.length; i++) {{
    const x = pad.l + (i / (points.length - 1)) * cW;
    const y = pad.t + ((maxV - points[i].val) / rangeV) * cH;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }}
  ctx.stroke();

  // Fill
  const lastX = pad.l + cW;
  const zeroY = pad.t + ((maxV - 0) / rangeV) * cH;
  ctx.lineTo(lastX, zeroY);
  ctx.lineTo(pad.l, zeroY);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + cH);
  if (points[points.length-1].val >= 0) {{
    grad.addColorStop(0, 'rgba(94,232,183,0.15)');
    grad.addColorStop(1, 'rgba(94,232,183,0)');
  }} else {{
    grad.addColorStop(0, 'rgba(240,104,136,0)');
    grad.addColorStop(1, 'rgba(240,104,136,0.15)');
  }}
  ctx.fillStyle = grad;
  ctx.fill();

  // X-axis dates
  ctx.fillStyle = '#7878a0'; ctx.font = '10px JetBrains Mono'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(points.length / 6));
  for (let i = 0; i < points.length; i += step) {{
    const x = pad.l + (i / (points.length - 1)) * cW;
    const d = points[i].ts.substring(5, 10);
    ctx.fillText(d, x, H - 8);
  }}
}}
drawChart();
window.addEventListener('resize', drawChart);

// ── Table sorting ──
document.querySelectorAll('.comp th').forEach(th => {{
  th.addEventListener('click', () => {{
    const table = document.getElementById('compTable');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const col = parseInt(th.dataset.col);
    const isNum = th.dataset.type === 'num';
    const asc = th.classList.contains('sorted-asc');

    table.querySelectorAll('th').forEach(h => h.classList.remove('sorted-asc','sorted-desc'));
    th.classList.add(asc ? 'sorted-desc' : 'sorted-asc');

    rows.sort((a, b) => {{
      let av, bv;
      if (isNum) {{
        av = parseFloat(a.children[col]?.dataset?.v || a.children[col]?.textContent) || 0;
        bv = parseFloat(b.children[col]?.dataset?.v || b.children[col]?.textContent) || 0;
      }} else {{
        av = a.children[col]?.textContent || '';
        bv = b.children[col]?.textContent || '';
      }}
      return asc ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1);
    }});
    rows.forEach(r => tbody.appendChild(r));
  }});
}});

// ── Tier filters ──
document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const tier = btn.dataset.tier;
    document.querySelectorAll('.comp tbody tr').forEach(row => {{
      row.style.display = (tier === 'all' || row.dataset.tier === tier) ? '' : 'none';
    }});
    // Also hide detail panels
    document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
    document.querySelectorAll('.comp tbody tr').forEach(r => r.classList.remove('expanded'));
  }});
}});

// ── Expand/collapse detail ──
function toggleDetail(key) {{
  const panel = document.getElementById('detail-' + key);
  const row = document.querySelector(`tr[onclick*="${{key}}"]`);
  if (!panel) return;
  const visible = panel.style.display !== 'none';
  // Close all
  document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.comp tbody tr').forEach(r => r.classList.remove('expanded'));
  if (!visible) {{
    panel.style.display = 'block';
    if (row) row.classList.add('expanded');
    panel.scrollIntoView({{ behavior:'smooth', block:'nearest' }});
  }}
}}

// ── Tabs ──
function switchTab(key, tab) {{
  const panel = document.getElementById('detail-' + key);
  if (!panel) return;
  panel.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
  panel.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + key + '-' + tab).style.display = 'block';
  event.target.classList.add('active');
}}
</script>
</body>
</html>"""
    return html


# =============================================================================
# MAIN
# =============================================================================

def generate_dashboard():
    """Main entry point."""
    print("[INFO] Generating dashboard...")

    portfolios = discover_portfolios()
    if not portfolios:
        print("[WARN] No portfolio files found")
        html = f"""<!DOCTYPE html><html><head><title>Polymarket Bot</title>
<style>body{{background:#0a0a12;color:#c8c8d8;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;}}
</style></head><body><div><h1 style="color:#5ee8b7">▲ Polymarket Bot</h1><p>No portfolio files found. Run the bot first.</p></div></body></html>"""
        with open("dashboard.html", "w") as f:
            f.write(html)
        return

    print(f"[INFO] Found {len(portfolios)} portfolios")

    # Batch fetch market data
    all_mids = collect_all_market_ids(portfolios)
    market_data = batch_fetch_markets(all_mids) if all_mids else {}

    # Update history
    history = update_pnl_history(portfolios, market_data)

    # Compute stats
    all_stats = []
    for strat_key, data in portfolios.items():
        stats = compute_strategy_stats(strat_key, data, market_data)
        all_stats.append(stats)

    # Generate
    html = generate_html(all_stats, market_data, history)

    with open("dashboard.html", "w") as f:
        f.write(html)
    # Also write index.html for GitHub Pages
    with open("index.html", "w") as f:
        f.write(html)

    print(f"[INFO] Dashboard generated ({len(all_stats)} strategies)")


if __name__ == "__main__":
    generate_dashboard()
