#!/usr/bin/env python3
"""
POLYMARKET BOT - Dashboard Generator (v3)
==========================================
Generates a single-page HTML dashboard with:
- Live trading section (pending trades with copiable IDs, live positions)
- Paper trading section (strategy comparison, P&L history)
- Mobile-friendly design

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
PENDING_TRADES_FILE = "pending_trades.json"
LIVE_PORTFOLIO_FILE = "live_portfolio.json"


def compact_history(history: list) -> list:
    if len(history) < 10:
        return history
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT")
    recent = []
    older = {}
    for entry in history:
        ts = entry.get("ts", "")
        if ts >= cutoff:
            recent.append(entry)
        else:
            day = ts[:10]
            older[day] = entry
    return sorted(older.values(), key=lambda e: e["ts"]) + recent


# =============================================================================
# DATA LOADING
# =============================================================================

def discover_portfolios() -> Dict[str, dict]:
    portfolios = {}
    for filepath in sorted(glob.glob("portfolio_*.json")):
        strat_key = filepath.replace("portfolio_", "").replace(".json", "")
        # Skip live portfolios
        if strat_key.startswith("live") or strat_key == "test_live":
            continue
        try:
            with open(filepath) as f:
                data = json.load(f)
            portfolios[strat_key] = data
        except Exception as e:
            print(f"[WARN] Failed to load {filepath}: {e}")
    return portfolios


def load_pending_trades() -> list:
    if not os.path.exists(PENDING_TRADES_FILE):
        return []
    try:
        with open(PENDING_TRADES_FILE) as f:
            return json.load(f)
    except:
        return []


def load_live_portfolio() -> dict:
    if not os.path.exists(LIVE_PORTFOLIO_FILE):
        return {"positions": [], "total_pnl": 0, "wins": 0, "losses": 0}
    try:
        with open(LIVE_PORTFOLIO_FILE) as f:
            return json.load(f)
    except:
        return {"positions": [], "total_pnl": 0, "wins": 0, "losses": 0}


def discover_live_portfolios() -> Dict[str, dict]:
    """Find live/test_live portfolio files."""
    portfolios = {}
    for filepath in sorted(glob.glob("portfolio_*.json")):
        strat_key = filepath.replace("portfolio_", "").replace(".json", "")
        if strat_key.startswith("test_live") or strat_key == "live":
            try:
                with open(filepath) as f:
                    portfolios[strat_key] = json.load(f)
            except:
                pass
    # Also check live_portfolio.json
    if os.path.exists(LIVE_PORTFOLIO_FILE):
        try:
            with open(LIVE_PORTFOLIO_FILE) as f:
                portfolios["live_executed"] = json.load(f)
        except:
            pass
    return portfolios


def get_strategy_meta(strat_key: str) -> dict:
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
    return {"name": strat_key, "description": "", "bet_side": "NO", "bankroll": 5000}


def collect_all_market_ids(portfolios: Dict[str, dict], live_portfolios: Dict[str, dict] = None) -> set:
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
    if live_portfolios:
        for data in live_portfolios.values():
            for pos in data.get("positions", []):
                mid = pos.get("market_id")
                if mid:
                    ids.add(mid)
    return ids


def batch_fetch_markets(market_ids: set) -> Dict[str, dict]:
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
        except:
            pass
    print(f"[INFO] Got data for {len(markets)}/{len(ids_list)} markets")
    return markets


# =============================================================================
# P&L HISTORY
# =============================================================================

def update_pnl_history(portfolios: Dict[str, dict], market_data: Dict[str, dict]):
    try:
        with open(HISTORY_FILE) as f:
            history = json.load(f)
    except:
        history = []

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"ts": now_iso, "strategies": {}}

    for strat_key, data in portfolios.items():
        realized = data.get("total_pnl", 0)
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

def compute_strategy_stats(strat_key: str, data: dict, market_data: Dict[str, dict]) -> dict:
    meta = get_strategy_meta(strat_key)
    initial = data.get("bankroll_initial", 5000)
    current = data.get("bankroll_current", initial)
    realized = data.get("total_pnl", 0)
    wins = data.get("wins", 0)
    losses = data.get("losses", 0)
    total_trades = data.get("total_trades", 0)
    positions = [p for p in data.get("positions", []) if p.get("status") == "open"]
    closed = data.get("closed_trades", [])

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


def get_tier(key: str) -> str:
    if key in ("conservative", "balanced", "aggressive", "volume_sweet"):
        return "base"
    for t in ("t1_", "t2_", "t3_", "t4_", "t5_"):
        if key.startswith(t):
            return t.rstrip("_")
    return "other"


def tier_label(tier: str) -> str:
    labels = {
        "base": "Base",
        "t1": "T1 Controls",
        "t2": "T2 Volume",
        "t3": "T3 Multi-Bucket",
        "t4": "T4 Cash",
        "t5": "T5 Deployable",
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
    pending_trades: list,
    live_portfolios: Dict[str, dict],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Aggregate paper stats ──
    total_realized = sum(s["realized"] for s in all_stats)
    total_unrealized = sum(s["unrealized"] for s in all_stats)
    total_open = sum(s["open_count"] for s in all_stats)
    total_closed = sum(s["closed_count"] for s in all_stats)
    total_wins = sum(s["wins"] for s in all_stats)
    total_losses = sum(s["losses"] for s in all_stats)
    agg_wr = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
    agg_pnl_cls = "pos" if (total_realized + total_unrealized) >= 0 else "neg"

    # ── Pending trades HTML ──
    pending_active = [t for t in pending_trades if t.get("status") == "pending"]
    pending_html = ""
    if pending_active:
        rows = ""
        for t in pending_active:
            price_pct = f"{t.get('proposed_price', 0):.0%}"
            size = f"${t.get('size_usd', 0):.2f}"
            cluster = t.get("cluster", "")
            question = (t.get("question", ""))[:55]
            tid = t.get("id", "")
            expires = (t.get("expires_at", ""))[:16].replace("T", " ")
            rows += f"""<tr>
<td class="trade-id" onclick="copyId('{tid}')" title="Click to copy">{tid}</td>
<td class="q-cell">{question}</td>
<td>{t.get('bet_side', 'NO')}</td>
<td>{price_pct}</td>
<td>{size}</td>
<td>{cluster}</td>
<td class="expires">{expires}</td>
</tr>\n"""
        pending_html = f"""
<div class="card">
  <div class="card-header">
    <h3>⏳ Pending Trades <span class="count">{len(pending_active)}</span></h3>
    <p class="hint">Click an ID to copy it for execution</p>
  </div>
  <div class="table-wrap">
  <table class="data-table">
  <thead><tr>
    <th>Trade ID</th><th>Market</th><th>Side</th><th>Price</th><th>Size</th><th>Cluster</th><th>Expires</th>
  </tr></thead>
  <tbody>{rows}</tbody>
  </table>
  </div>
</div>"""
    else:
        pending_html = """
<div class="card empty-card">
  <p>No pending trades. Next scan in ~6 hours.</p>
</div>"""

    # ── Live positions HTML ──
    live_positions_html = ""
    live_total_pnl = 0
    live_open = 0
    live_closed_count = 0
    live_wins = 0
    live_losses = 0

    for lp_key, lp_data in live_portfolios.items():
        positions = lp_data.get("positions", [])
        closed_trades = lp_data.get("closed_trades", [])
        live_total_pnl += lp_data.get("total_pnl", 0)
        live_wins += lp_data.get("wins", 0)
        live_losses += lp_data.get("losses", 0)

        open_pos = [p for p in positions if p.get("status") == "open"]
        live_open += len(open_pos)
        live_closed_count += len(closed_trades)

        if open_pos:
            rows = ""
            for pos in open_pos:
                mid = pos.get("market_id", "")
                mkt = market_data.get(mid, {})
                question = (pos.get("question") or mkt.get("question", mid))[:55]
                ep = pos.get("entry_price", 0)
                bs = pos.get("bet_side", "NO")
                size = pos.get("size_usd", 0)
                cluster = pos.get("cluster", "")
                entry_d = (pos.get("entry_date") or "")[:10]

                cy = mkt.get("price_yes")
                if cy is not None:
                    if bs == "NO":
                        unr = ((1 - cy) - ep) * pos.get("shares", 0)
                    else:
                        unr = (cy - ep) * pos.get("shares", 0)
                    cur_str = f"{cy:.0%}"
                    pnl_str = f"${unr:+,.2f}"
                    pnl_cls = "pos" if unr >= 0 else "neg"
                else:
                    cur_str = "—"
                    pnl_str = "—"
                    pnl_cls = ""

                entry_yes = (1 - ep) if bs == "NO" else ep
                slug = mkt.get("slug", "")
                link = f"https://polymarket.com/event/{slug}" if slug else "#"

                rows += f"""<tr>
<td class="q-cell"><a href="{link}" target="_blank">{question}</a></td>
<td><span class="badge badge-{bs.lower()}">{bs}</span></td>
<td>{entry_yes:.0%}</td><td>{cur_str}</td>
<td class="{pnl_cls}">{pnl_str}</td>
<td>${size:.2f}</td><td>{cluster}</td><td>{entry_d}</td>
</tr>\n"""

            live_positions_html += f"""
<div class="card">
  <div class="card-header"><h3>📊 Live Positions <span class="count">{len(open_pos)}</span></h3></div>
  <div class="table-wrap">
  <table class="data-table">
  <thead><tr>
    <th>Market</th><th>Side</th><th>Entry YES</th><th>Current</th><th>P&L</th><th>Size</th><th>Cluster</th><th>Date</th>
  </tr></thead>
  <tbody>{rows}</tbody>
  </table>
  </div>
</div>"""

    if not live_positions_html and not pending_active:
        live_positions_html = """
<div class="card empty-card">
  <p>No live positions yet.</p>
</div>"""

    live_pnl_cls = "pos" if live_total_pnl >= 0 else "neg"

    # ── Paper comparison rows ──
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

    # ── Detail panels ──
    detail_panels = ""
    for s in all_stats:
        open_rows = ""
        for pos in sorted(s["positions"], key=lambda p: p.get("entry_date", ""), reverse=True):
            mid = pos.get("market_id", "")
            mkt = market_data.get(mid, {})
            question = (pos.get("question") or mkt.get("question", mid))[:60]
            slug = mkt.get("slug", "")
            link = f"https://polymarket.com/event/{slug}" if slug else "#"
            ep = pos.get("entry_price", 0)
            sh = pos.get("shares", 0)
            bs = pos.get("bet_side", "NO")
            size = pos.get("size_usd", 0)
            cluster = pos.get("cluster", "")
            entry_d = (pos.get("entry_date") or "")[:10]
            cy = mkt.get("price_yes")
            entry_yes = (1 - ep) if bs == "NO" else ep
            if cy is not None:
                unr = ((1 - cy) - ep) * sh if bs == "NO" else (cy - ep) * sh
                cur_str = f"{cy:.0%}"
                pnl_str = f"${unr:+,.0f}"
                pnl_cls = "pos" if unr >= 0 else "neg"
            else:
                cur_str = "—"
                pnl_str = "—"
                pnl_cls = ""
            open_rows += f"""<tr>
<td class="q-cell"><a href="{link}" target="_blank">{question}</a></td>
<td><span class="badge badge-{bs.lower()}">{bs}</span></td>
<td data-v="{entry_yes:.4f}">{entry_yes:.0%}</td><td data-v="{cy if cy is not None else 0:.4f}">{cur_str}</td>
<td class="{pnl_cls}" data-v="{unr if cy is not None else 0:.2f}">{pnl_str}</td>
<td data-v="{size:.2f}">${size:.0f}</td><td>{cluster}</td><td data-v="{(pos.get('entry_date') or '')[:10]}">{entry_d}</td>
</tr>\n"""

        closed_rows = ""
        for pos in sorted(s["closed_trades"], key=lambda p: p.get("close_date") or p.get("entry_date", ""), reverse=True)[:30]:
            question = (pos.get("question") or "")[:60]
            ep = pos.get("entry_price", 0)
            bs = pos.get("bet_side", "NO")
            pnl = pos.get("pnl", 0)
            res = pos.get("resolution", "")
            entry_d = (pos.get("entry_date") or "")[:10]
            close_d = (pos.get("close_date") or "")[:10]
            entry_yes = (1 - ep) if bs == "NO" else ep
            pnl_cls = "pos" if pnl and pnl > 0 else "neg"
            closed_rows += f"""<tr>
<td class="q-cell">{question}</td>
<td><span class="badge badge-{bs.lower()}">{bs}</span></td>
<td data-v="{entry_yes:.4f}">{entry_yes:.0%}</td>
<td class="{'pos' if res=='win' else 'neg'}" data-v="{'1' if res=='win' else '0'}"><span class="badge badge-{res}">{res}</span></td>
<td class="{pnl_cls}" data-v="{pnl:.2f}">${pnl:+,.0f}</td>
<td data-v="{entry_d}">{entry_d}</td><td data-v="{close_d}">{close_d}</td>
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
      Bankroll: ${s['current']:,.0f} · Exposure: ${s['exposure']:,.0f} ({s['exposure_pct']:.0f}%)
      {(' · ' + cluster_tags) if cluster_tags else ''}
    </div>
  </div>
  <div class="detail-tabs">
    <button class="tab-btn active" onclick="switchTab('{s['key']}','open')">Open ({s['open_count']})</button>
    <button class="tab-btn" onclick="switchTab('{s['key']}','closed')">Closed ({s['closed_count']})</button>
  </div>
  <div class="tab-content" id="tab-{s['key']}-open">
    {f'<div class="table-wrap"><table class="data-table sm sortable"><thead><tr><th data-col="0" data-type="str">Market</th><th data-col="1" data-type="str">Side</th><th data-col="2" data-type="num">Entry</th><th data-col="3" data-type="num">Current</th><th data-col="4" data-type="num">P&L</th><th data-col="5" data-type="num">Size</th><th data-col="6" data-type="str">Cluster</th><th data-col="7" data-type="str">Date</th></tr></thead><tbody>' + open_rows + '</tbody></table></div>' if open_rows else '<p class="empty">No open positions</p>'}
  </div>
  <div class="tab-content" id="tab-{s['key']}-closed" style="display:none">
    {f'<div class="table-wrap"><table class="data-table sm sortable"><thead><tr><th data-col="0" data-type="str">Market</th><th data-col="1" data-type="str">Side</th><th data-col="2" data-type="num">Entry</th><th data-col="3" data-type="num">Result</th><th data-col="4" data-type="num">P&L</th><th data-col="5" data-type="str">Opened</th><th data-col="6" data-type="str">Closed</th></tr></thead><tbody>' + closed_rows + '</tbody></table></div>' if closed_rows else '<p class="empty">No closed trades</p>'}
  </div>
</div>\n"""

    # ── History JSON ──
    history_json = json.dumps(history[-100:]) if history else "[]"

    # ── Tier filter buttons ──
    tiers_present = sorted(set(get_tier(s["key"]) for s in all_stats))
    tier_btns = '<button class="filter-btn active" data-tier="all">All</button>'
    for t in tiers_present:
        tier_btns += f'<button class="filter-btn" data-tier="{t}">{tier_label(t)}</button>'

    # ── Full HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="360">
<title>Polymarket Bot</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700&family=DM+Mono:wght@400;500&display=swap');

:root {{
  --bg: #0c0c14;
  --bg2: #13131f;
  --bg3: #1b1b2b;
  --bg-hover: #22223a;
  --border: #262640;
  --text: #cccce0;
  --text2: #6e6e90;
  --accent: #00e5a0;
  --accent-dim: rgba(0,229,160,0.12);
  --neg: #ff5c7c;
  --neg-dim: rgba(255,92,124,0.12);
  --blue: #5c9eff;
  --warn: #ffb84d;
  --warn-dim: rgba(255,184,77,0.12);
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; font-size:17px; -webkit-font-smoothing:antialiased; }}

.wrap {{ max-width:1400px; margin:0 auto; padding:20px 16px; }}

/* ── Header ── */
header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; flex-wrap:wrap; gap:8px; }}
header h1 {{ font-size:1.6em; font-weight:700; color:#fff; }}
header h1 .logo {{ color:var(--accent); }}
.updated {{ font-size:0.75em; color:var(--text2); font-family:'DM Mono',monospace; }}

/* ── Tab Navigation ── */
.main-tabs {{ display:flex; gap:2px; margin-bottom:20px; background:var(--bg2); border-radius:10px; padding:3px; border:1px solid var(--border); }}
.main-tab {{
  flex:1; text-align:center; padding:10px 16px; border-radius:8px;
  font-weight:600; font-size:0.9em; cursor:pointer; transition:all .15s;
  border:none; background:none; color:var(--text2); font-family:'DM Sans',sans-serif;
}}
.main-tab:hover {{ color:var(--text); }}
.main-tab.active {{ background:var(--accent); color:var(--bg); }}
.main-tab .tab-count {{ font-size:0.8em; opacity:0.7; margin-left:4px; }}

.tab-panel {{ display:none; }}
.tab-panel.active {{ display:block; }}

/* ── Stats Bar ── */
.stats-bar {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(100px, 1fr)); gap:8px; margin-bottom:20px; }}
.stat {{
  background:var(--bg2); border:1px solid var(--border); border-radius:8px;
  padding:12px 14px; text-align:center;
}}
.stat-val {{ display:block; font-family:'DM Mono',monospace; font-size:1.4em; font-weight:700; }}
.stat-lbl {{ font-size:0.75em; color:var(--text2); text-transform:uppercase; letter-spacing:0.05em; margin-top:2px; }}

/* ── Cards ── */
.card {{
  background:var(--bg2); border:1px solid var(--border); border-radius:10px;
  margin-bottom:12px; overflow:hidden;
}}
.card-header {{ padding:14px 16px 8px; }}
.card-header h3 {{ font-size:0.95em; color:#fff; font-weight:600; }}
.card-header .count {{
  display:inline-block; background:var(--accent-dim); color:var(--accent);
  font-size:0.75em; padding:2px 8px; border-radius:10px; margin-left:6px; font-weight:700;
}}
.card-header .hint {{ font-size:0.72em; color:var(--text2); margin-top:2px; }}
.empty-card {{ padding:24px; text-align:center; color:var(--text2); font-size:0.85em; }}

/* ── Tables ── */
.table-wrap {{ overflow-x:auto; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:0.92em; }}
.data-table th {{
  text-align:left; padding:10px 12px; color:var(--text2); font-weight:500;
  border-bottom:1px solid var(--border); font-size:0.82em;
  text-transform:uppercase; letter-spacing:0.03em; white-space:nowrap;
  cursor:pointer; user-select:none; transition:color .1s;
}}
.data-table th:hover {{ color:var(--accent); }}
.data-table th.sorted-asc::after {{ content:" ▲"; font-size:0.6em; }}
.data-table th.sorted-desc::after {{ content:" ▼"; font-size:0.6em; }}
.data-table td {{
  padding:8px 12px; border-bottom:1px solid rgba(38,38,64,0.5);
  font-family:'DM Mono',monospace; font-size:0.95em; white-space:nowrap;
}}
.data-table.sm td {{ font-size:0.9em; padding:7px 10px; }}

.trade-id {{
  color:var(--blue); cursor:pointer; font-size:0.82em;
  user-select:all; transition:color .1s;
}}
.trade-id:hover {{ color:var(--accent); }}
.trade-id:active {{ color:#fff; }}

.q-cell {{ font-family:'DM Sans',sans-serif; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.q-cell a {{ color:var(--blue); text-decoration:none; }}
.q-cell a:hover {{ text-decoration:underline; }}
.expires {{ color:var(--text2); font-size:0.85em; }}

.badge {{ padding:3px 8px; border-radius:4px; font-size:0.82em; font-weight:600; }}
.badge-no {{ background:var(--neg-dim); color:var(--neg); }}
.badge-yes {{ background:var(--accent-dim); color:var(--accent); }}
.badge-win {{ background:var(--accent-dim); color:var(--accent); }}
.badge-lose {{ background:var(--neg-dim); color:var(--neg); }}

.pos {{ color:var(--accent); }}
.neg {{ color:var(--neg); }}

/* ── Comparison table ── */
.comp {{ width:100%; border-collapse:collapse; font-size:0.92em; }}
.comp th {{
  text-align:left; padding:10px 12px; color:var(--text2); font-weight:500;
  border-bottom:2px solid var(--border); cursor:pointer; white-space:nowrap;
  font-size:0.8em; text-transform:uppercase; letter-spacing:0.03em;
  user-select:none; position:sticky; top:0; background:var(--bg);
}}
.comp th:hover {{ color:var(--accent); }}
.comp th.sorted-asc::after {{ content:" ▲"; font-size:0.6em; }}
.comp th.sorted-desc::after {{ content:" ▼"; font-size:0.6em; }}
.comp td {{
  padding:8px 12px; border-bottom:1px solid var(--border);
  font-family:'DM Mono',monospace; font-size:0.95em; white-space:nowrap;
}}
.comp tr {{ cursor:pointer; transition:background .1s; }}
.comp tr:hover {{ background:var(--bg-hover); }}
.comp tr.expanded {{ background:var(--bg3); }}
.strat-name {{ font-family:'DM Sans',sans-serif; font-weight:600; color:#fff; }}

.tier-dot {{ display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:5px; }}
.tier-base {{ background:var(--text2); }}
.tier-t1 {{ background:var(--blue); }}
.tier-t2 {{ background:var(--warn); }}
.tier-t3 {{ background:#b070e0; }}
.tier-t4 {{ background:#f08060; }}
.tier-t5 {{ background:var(--accent); }}
.tier-other {{ background:#555; }}

/* ── Chart ── */
.chart-wrap {{ margin:20px 0; }}
.chart-wrap h2 {{ font-size:1em; margin-bottom:10px; color:#fff; }}
#chart {{ width:100%; height:240px; background:var(--bg2); border:1px solid var(--border); border-radius:10px; }}

/* ── Filters ── */
.filters {{ display:flex; gap:5px; margin-bottom:12px; flex-wrap:wrap; }}
.filter-btn {{
  background:var(--bg2); border:1px solid var(--border); color:var(--text2);
  padding:6px 14px; border-radius:6px; font-size:0.82em; cursor:pointer;
  font-family:'DM Sans',sans-serif; transition:all .15s;
}}
.filter-btn:hover {{ border-color:var(--accent); color:var(--text); }}
.filter-btn.active {{ background:var(--accent); color:var(--bg); border-color:var(--accent); font-weight:600; }}

/* ── Detail panels ── */
.detail-panel {{
  background:var(--bg2); border:1px solid var(--border); border-radius:10px;
  margin-bottom:6px; overflow:hidden; animation:slideDown .2s ease;
}}
@keyframes slideDown {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
.detail-header {{ padding:14px 16px 6px; }}
.detail-header h3 {{ font-size:0.95em; color:#fff; }}
.desc {{ color:var(--text2); font-size:0.85em; margin:2px 0 4px; }}
.detail-meta {{ font-size:0.82em; color:var(--text2); }}
.detail-tabs {{ padding:0 16px; display:flex; gap:4px; }}
.tab-btn {{
  background:none; border:none; color:var(--text2); padding:8px 14px;
  font-family:'DM Sans',sans-serif; font-size:0.88em; cursor:pointer;
  border-bottom:2px solid transparent; transition:all .15s;
}}
.tab-btn:hover {{ color:var(--text); }}
.tab-btn.active {{ color:var(--accent); border-bottom-color:var(--accent); }}
.tab-content {{ padding:0 16px 14px; }}
.tag {{ display:inline-block; padding:1px 7px; background:var(--bg3); border-radius:3px; font-size:0.75em; margin:0 2px; }}
.empty {{ color:var(--text2); font-size:0.82em; padding:14px 0; }}

/* ── Toast ── */
.toast {{
  position:fixed; bottom:20px; left:50%; transform:translateX(-50%) translateY(80px);
  background:var(--accent); color:var(--bg); padding:10px 20px; border-radius:8px;
  font-weight:600; font-size:0.85em; opacity:0; transition:all .3s ease;
  pointer-events:none; z-index:100;
}}
.toast.show {{ opacity:1; transform:translateX(-50%) translateY(0); }}

/* ── Responsive ── */
@media (max-width:768px) {{
  body {{ font-size:15px; }}
  .stats-bar {{ grid-template-columns:repeat(2, 1fr); }}
  .stat-val {{ font-size:1.2em; }}
  .comp {{ font-size:0.82em; }}
  .q-cell {{ max-width:160px; }}
  .trade-id {{ font-size:0.8em; }}
  header h1 {{ font-size:1.3em; }}
}}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1><span class="logo">◆</span> Polymarket Bot</h1>
  <span class="updated">{now}</span>
</header>

<div class="main-tabs">
  <button class="main-tab active" onclick="switchMain('live')">Live Trading <span class="tab-count">{len(pending_active) + live_open}</span></button>
  <button class="main-tab" onclick="switchMain('paper')">Paper Trading <span class="tab-count">{len(all_stats)}</span></button>
</div>

<!-- ═══════════ LIVE TRADING ═══════════ -->
<div class="tab-panel active" id="panel-live">

<div class="stats-bar">
  <div class="stat"><span class="stat-val" style="color:var(--warn)">{len(pending_active)}</span><span class="stat-lbl">Pending</span></div>
  <div class="stat"><span class="stat-val">{live_open}</span><span class="stat-lbl">Open</span></div>
  <div class="stat"><span class="stat-val {live_pnl_cls}">${live_total_pnl:+,.2f}</span><span class="stat-lbl">P&L</span></div>
  <div class="stat"><span class="stat-val">{live_wins}W/{live_losses}L</span><span class="stat-lbl">Record</span></div>
</div>

{pending_html}
{live_positions_html}

</div>

<!-- ═══════════ PAPER TRADING ═══════════ -->
<div class="tab-panel" id="panel-paper">

<div class="chart-wrap">
  <h2>P&L History</h2>
  <canvas id="chart"></canvas>
</div>

<div class="filters">{tier_btns}</div>

<div class="table-wrap">
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

<div class="toast" id="toast">Copied!</div>

</div>

<script>
// ── Main tab switching ──
function switchMain(tab) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.main-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + tab).classList.add('active');
  event.target.closest('.main-tab').classList.add('active');
  if (tab === 'paper') drawChart();
}}

// ── Copy trade ID ──
function copyId(id) {{
  navigator.clipboard.writeText(id).then(() => {{
    const toast = document.getElementById('toast');
    toast.textContent = 'Copied: ' + id;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
  }});
}}

// ── P&L Chart ──
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
  const pad = {{t:20, r:20, b:30, l:55}};
  const cW = W - pad.l - pad.r, cH = H - pad.t - pad.b;

  const points = history.map(h => {{
    let total = 0;
    for (const s of Object.values(h.strategies)) total += (s.total || 0);
    return {{ ts: h.ts, val: total }};
  }});

  if (points.length < 2) {{
    ctx.fillStyle = '#6e6e90'; ctx.font = '13px DM Sans';
    ctx.fillText('Need more data points...', W/2 - 70, H/2);
    return;
  }}

  const vals = points.map(p => p.val);
  let minV = Math.min(...vals, 0), maxV = Math.max(...vals, 0);
  if (minV === maxV) {{ minV -= 10; maxV += 10; }}
  const rangeV = maxV - minV;

  ctx.strokeStyle = '#262640'; ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {{
    const y = pad.t + (cH / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
    ctx.fillStyle = '#6e6e90'; ctx.font = '11px DM Mono';
    ctx.textAlign = 'right';
    ctx.fillText('$' + (maxV - (rangeV / 4) * i).toFixed(0), pad.l - 8, y + 4);
  }}

  if (minV < 0 && maxV > 0) {{
    const zeroY = pad.t + (maxV / rangeV) * cH;
    ctx.strokeStyle = '#3a3a5a'; ctx.lineWidth = 1; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l, zeroY); ctx.lineTo(W - pad.r, zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }}

  ctx.beginPath();
  ctx.strokeStyle = points[points.length-1].val >= 0 ? '#00e5a0' : '#ff5c7c';
  ctx.lineWidth = 2; ctx.lineJoin = 'round';
  for (let i = 0; i < points.length; i++) {{
    const x = pad.l + (i / (points.length - 1)) * cW;
    const y = pad.t + ((maxV - points[i].val) / rangeV) * cH;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }}
  ctx.stroke();

  const lastX = pad.l + cW;
  const zeroY = pad.t + (maxV / rangeV) * cH;
  ctx.lineTo(lastX, zeroY); ctx.lineTo(pad.l, zeroY); ctx.closePath();
  const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + cH);
  if (points[points.length-1].val >= 0) {{
    grad.addColorStop(0, 'rgba(0,229,160,0.12)'); grad.addColorStop(1, 'rgba(0,229,160,0)');
  }} else {{
    grad.addColorStop(0, 'rgba(255,92,124,0)'); grad.addColorStop(1, 'rgba(255,92,124,0.12)');
  }}
  ctx.fillStyle = grad; ctx.fill();

  ctx.fillStyle = '#6e6e90'; ctx.font = '10px DM Mono'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(points.length / 6));
  for (let i = 0; i < points.length; i += step) {{
    const x = pad.l + (i / (points.length - 1)) * cW;
    ctx.fillText(points[i].ts.substring(5, 10), x, H - 8);
  }}
}}

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
    document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
    document.querySelectorAll('.comp tbody tr').forEach(r => r.classList.remove('expanded'));
  }});
}});

// ── Expand/collapse detail ──
function toggleDetail(key) {{
  const panel = document.getElementById('detail-' + key);
  if (!panel) return;
  const visible = panel.style.display !== 'none';
  document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.comp tbody tr').forEach(r => r.classList.remove('expanded'));
  if (!visible) {{
    panel.style.display = 'block';
    const row = document.querySelector(`tr[onclick*="${{key}}"]`);
    if (row) row.classList.add('expanded');
    panel.scrollIntoView({{ behavior:'smooth', block:'nearest' }});
  }}
}}

function switchTab(key, tab) {{
  const panel = document.getElementById('detail-' + key);
  if (!panel) return;
  panel.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
  panel.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + key + '-' + tab).style.display = 'block';
  event.target.classList.add('active');
}}

// ── Sortable detail tables ──
document.querySelectorAll('.data-table.sortable th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const table = th.closest('table');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const col = parseInt(th.dataset.col);
    const isNum = th.dataset.type === 'num';
    const asc = th.classList.contains('sorted-asc');
    table.querySelectorAll('th').forEach(h => h.classList.remove('sorted-asc','sorted-desc'));
    th.classList.add(asc ? 'sorted-desc' : 'sorted-asc');
    rows.sort((a, b) => {{
      const ac = a.children[col], bc = b.children[col];
      let av, bv;
      if (isNum) {{
        av = parseFloat(ac?.dataset?.v || ac?.textContent) || 0;
        bv = parseFloat(bc?.dataset?.v || bc?.textContent) || 0;
      }} else {{
        av = ac?.dataset?.v || ac?.textContent || '';
        bv = bc?.dataset?.v || bc?.textContent || '';
      }}
      return asc ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1);
    }});
    rows.forEach(r => tbody.appendChild(r));
  }});
}});
</script>
</body>
</html>"""
    return html


# =============================================================================
# MAIN
# =============================================================================

def generate_dashboard():
    print("[INFO] Generating dashboard v3...")

    portfolios = discover_portfolios()
    live_portfolios = discover_live_portfolios()
    pending_trades = load_pending_trades()

    if not portfolios and not live_portfolios and not pending_trades:
        html = """<!DOCTYPE html><html><head><title>Polymarket Bot</title>
<style>body{background:#0c0c14;color:#cccce0;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;}
</style></head><body><div><h1 style="color:#00e5a0">◆ Polymarket Bot</h1><p>No data yet. Run the bot first.</p></div></body></html>"""
        with open("dashboard.html", "w", encoding="utf-8") as f:
            f.write(html)
        return

    print(f"[INFO] Found {len(portfolios)} paper + {len(live_portfolios)} live portfolios, {len(pending_trades)} pending trades")

    all_mids = collect_all_market_ids(portfolios, live_portfolios)
    market_data = batch_fetch_markets(all_mids) if all_mids else {}

    history = update_pnl_history(portfolios, market_data)

    all_stats = []
    for strat_key, data in portfolios.items():
        stats = compute_strategy_stats(strat_key, data, market_data)
        all_stats.append(stats)

    html = generate_html(all_stats, market_data, history, pending_trades, live_portfolios)

    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[INFO] Dashboard v3 generated ({len(all_stats)} paper strategies, {len(pending_trades)} pending trades)")


if __name__ == "__main__":
    generate_dashboard()
