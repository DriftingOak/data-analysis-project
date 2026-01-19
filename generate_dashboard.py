#!/usr/bin/env python3
"""Generate a lightweight static dashboard (HTML) from portfolio_*.json.

Why:
- You get a simple interface to sanity-check what the bots bought/sold
- Works with GitHub Pages (static files)

Inputs (expected in repo root):
- portfolio_*.json (one per bot/strategy)
Optional:
- bot_history.json (if present, we show a small "last run" panel)

Output (default folder: site/):
- index.html
- data.json

No external dependencies.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def portfolio_name_from_file(fn: str) -> str:
    # portfolio_aggressive.json -> aggressive
    base = os.path.basename(fn)
    name = base.replace("portfolio_", "").replace(".json", "")
    return name


def normalize_position(p: Dict[str, Any]) -> Dict[str, Any]:
    """Accepts both old/new schemas and returns a normalized dict."""
    # Newer schema (your repo) typically uses:
    # market_id, question, bet_side, entry_date, entry_price, size_usd, shares,
    # cluster, expected_close, status, resolution, close_date, pnl
    # Older schema (my earlier internal sim) used: entry_ts, size_usdc, etc.

    market_id = str(p.get("market_id") or p.get("id") or "")
    question = p.get("question") or p.get("title") or ""
    bet_side = p.get("bet_side") or p.get("side") or ""

    entry_price = p.get("entry_price")
    if entry_price is None:
        entry_price = p.get("price")

    size_usd = p.get("size_usd")
    if size_usd is None:
        size_usd = p.get("size_usdc")

    shares = p.get("shares")
    if shares is None:
        shares = p.get("qty_shares")

    entry_date = p.get("entry_date") or p.get("entry_time")
    if entry_date is None and p.get("entry_ts") is not None:
        try:
            entry_date = datetime.fromtimestamp(float(p["entry_ts"]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        except Exception:
            entry_date = None

    expected_close = p.get("expected_close")
    if expected_close is None and p.get("close_ts") is not None:
        try:
            expected_close = datetime.fromtimestamp(float(p["close_ts"]), tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            expected_close = None

    cluster = p.get("cluster") or "other"

    status = p.get("status") or ("open" if p.get("resolution") in (None, "") else "closed")

    resolution = p.get("resolution")
    pnl = p.get("pnl")

    return {
        "market_id": market_id,
        "question": question,
        "bet_side": bet_side,
        "entry_date": entry_date,
        "entry_price": safe_float(entry_price, default=None) if entry_price is not None else None,
        "size_usd": safe_float(size_usd, default=None) if size_usd is not None else None,
        "shares": safe_float(shares, default=None) if shares is not None else None,
        "cluster": cluster,
        "expected_close": expected_close,
        "status": status,
        "resolution": resolution,
        "pnl": safe_float(pnl, default=None) if pnl is not None else None,
    }


def normalize_closed_trade(t: Dict[str, Any]) -> Dict[str, Any]:
    market_id = str(t.get("market_id") or t.get("id") or "")
    question = t.get("question") or t.get("title") or ""
    bet_side = t.get("bet_side") or t.get("side") or ""
    entry_price = t.get("entry_price")
    size_usd = t.get("size_usd") or t.get("size_usdc")

    close_date = t.get("close_date")
    if close_date is None and t.get("close_ts") is not None:
        try:
            close_date = datetime.fromtimestamp(float(t["close_ts"]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        except Exception:
            close_date = None

    resolution = t.get("resolution")
    pnl = t.get("pnl")

    return {
        "market_id": market_id,
        "question": question,
        "bet_side": bet_side,
        "entry_price": safe_float(entry_price, default=None) if entry_price is not None else None,
        "size_usd": safe_float(size_usd, default=None) if size_usd is not None else None,
        "close_date": close_date,
        "resolution": resolution,
        "pnl": safe_float(pnl, default=None) if pnl is not None else None,
    }


def compute_exposure(open_positions: List[Dict[str, Any]]) -> Tuple[float, Dict[str, float]]:
    total = 0.0
    by_cluster: Dict[str, float] = {}
    for p in open_positions:
        amt = safe_float(p.get("size_usd"), 0.0)
        total += amt
        cl = p.get("cluster") or "other"
        by_cluster[cl] = by_cluster.get(cl, 0.0) + amt
    # Sort clusters by exposure
    by_cluster = dict(sorted(by_cluster.items(), key=lambda kv: kv[1], reverse=True))
    return total, by_cluster


def maybe_make_market_url(market_id: str, slug: Optional[str] = None) -> str:
    # If you later store slug, we can use it.
    # For now, we still provide something click-able: the Gamma market endpoint.
    # You can always copy-paste the question into Polymarket search.
    if slug:
        return f"https://polymarket.com/market/{slug}"
    if market_id:
        return f"https://gamma-api.polymarket.com/markets/{market_id}"
    return ""


def build_data() -> Dict[str, Any]:
    portfolios: Dict[str, Any] = {}

    for fn in sorted(glob.glob("portfolio_*.json")):
        raw = load_json(fn)
        if not raw:
            continue

        name = portfolio_name_from_file(fn)

        positions_raw = raw.get("positions", []) or []
        closed_raw = raw.get("closed_trades", []) or []

        positions = [normalize_position(p) for p in positions_raw]
        closed = [normalize_closed_trade(t) for t in closed_raw]

        open_positions = [p for p in positions if (p.get("status") or "").lower() == "open"]

        exposure_total, exposure_by_cluster = compute_exposure(open_positions)

        # Top upcoming expiries
        def close_sort_key(p: Dict[str, Any]):
            # expected_close format "YYYY-MM-DD" or None
            return p.get("expected_close") or "9999-12-31"

        upcoming = sorted(open_positions, key=close_sort_key)[:15]

        # Recent closed
        recent_closed = closed
        # If close_date exists, sort desc
        if any(t.get("close_date") for t in closed):
            recent_closed = sorted(closed, key=lambda t: t.get("close_date") or "", reverse=True)
        recent_closed = recent_closed[:20]

        # Add URLs
        for p in open_positions:
            p["url"] = maybe_make_market_url(p.get("market_id", ""))
        for t in recent_closed:
            t["url"] = maybe_make_market_url(t.get("market_id", ""))

        portfolios[name] = {
            "file": fn,
            "bankroll_initial": safe_float(raw.get("bankroll_initial"), 0.0),
            "bankroll_current": safe_float(raw.get("bankroll_current"), 0.0),
            "entry_cost_rate": safe_float(raw.get("entry_cost_rate"), 0.0),
            "stats": {
                "total_trades": int(raw.get("total_trades") or 0),
                "wins": int(raw.get("wins") or 0),
                "losses": int(raw.get("losses") or 0),
                "total_pnl": safe_float(raw.get("total_pnl"), 0.0),
                "open_positions": len(open_positions),
                "closed_trades": len(closed),
                "exposure_total": exposure_total,
                "exposure_by_cluster": exposure_by_cluster,
            },
            "open_positions": open_positions,
            "upcoming": upcoming,
            "recent_closed": recent_closed,
        }

    bot_history = load_json("bot_history.json")

    return {
        "generated_at": utc_now_iso(),
        "portfolio_count": len(portfolios),
        "portfolios": portfolios,
        "bot_history": bot_history,
    }


def render_html() -> str:
    # Simple self-contained UI (no external assets)
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Polymarket Paper Trading Dashboard</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 20px; }
    h1 { margin: 0 0 4px 0; }
    .muted { color: #666; font-size: 14px; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
    @media (min-width: 1100px) { .grid { grid-template-columns: 370px 1fr; } }

    .card { border: 1px solid #ddd; border-radius: 10px; padding: 12px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    .tabs { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
    .tab { padding: 7px 10px; border: 1px solid #ccc; border-radius: 999px; cursor: pointer; user-select: none; font-size: 14px; }
    .tab.active { background: #111; color: white; border-color: #111; }

    .kpi { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .kpi .box { border: 1px solid #eee; border-radius: 10px; padding: 10px; }
    .kpi .value { font-weight: 700; font-size: 18px; }
    .kpi .label { color: #666; font-size: 12px; }

    .row { display: flex; gap: 10px; flex-wrap: wrap; }

    input[type=\"search\"] { width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ddd; font-size: 14px; }

    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #eee; vertical-align: top; }
    th { font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.04em; }
    td { font-size: 14px; }
    .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid #ddd; font-size: 12px; color: #333; }

    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
    .small { font-size: 12px; }

    a { color: inherit; }
    .right { text-align: right; }
    .good { color: #1a7f37; font-weight: 600; }
    .bad { color: #c11717; font-weight: 600; }
  </style>
</head>
<body>
  <h1>Polymarket Paper Trading Dashboard</h1>
  <div class=\"muted\">Auto-updated by GitHub Actions. Click any market to open its Gamma details.</div>

  <div class=\"tabs\" id=\"tabs\"></div>

  <div class=\"grid\">
    <div class=\"card\">
      <div id=\"meta\" class=\"muted\"></div>
      <div style=\"height: 8px\"></div>
      <div class=\"kpi\" id=\"kpis\"></div>
      <div style=\"height: 10px\"></div>
      <div class=\"small\" id=\"exposure\"></div>
    </div>

    <div class=\"card\">
      <div class=\"row\" style=\"justify-content: space-between; align-items:center\">
        <div>
          <div style=\"font-weight:700\">Open positions</div>
          <div class=\"muted small\" id=\"open_meta\"></div>
        </div>
        <div style=\"min-width: 320px; flex: 1\">
          <input id=\"search\" type=\"search\" placeholder=\"Search question / cluster / date...\" />
        </div>
      </div>

      <div style=\"height: 10px\"></div>
      <table id=\"open_table\"></table>

      <div style=\"height: 18px\"></div>
      <div style=\"font-weight:700\">Recently closed</div>
      <div style=\"height: 8px\"></div>
      <table id=\"closed_table\"></table>
    </div>
  </div>

<script>
let DATA = null;
let current = null;

function fmtMoney(x) {
  if (x === null || x === undefined || Number.isNaN(x)) return "-";
  return (Math.round(x * 100) / 100).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function fmtPct(x) {
  if (x === null || x === undefined || Number.isNaN(x)) return "-";
  return (Math.round(x * 1000) / 10).toFixed(1) + "%";
}

function byId(id){ return document.getElementById(id); }

function renderTabs(){
  const tabs = byId('tabs');
  tabs.innerHTML = '';
  const names = Object.keys(DATA.portfolios);
  if (names.length === 0) {
    tabs.innerHTML = '<div class="muted">No portfolio_*.json found.</div>';
    return;
  }
  names.forEach(name => {
    const el = document.createElement('div');
    el.className = 'tab' + (name === current ? ' active' : '');
    el.innerText = name;
    el.onclick = () => { current = name; renderAll(); };
    tabs.appendChild(el);
  });
}

function renderKPIs(p){
  const kpis = byId('kpis');
  const s = p.stats;
  const init = p.bankroll_initial || 0;
  const cur = p.bankroll_current || 0;
  const pnl = cur - init;
  const roi = init > 0 ? pnl / init : 0;

  const boxes = [
    {label:'Bankroll', value:`${fmtMoney(cur)} (init ${fmtMoney(init)})`},
    {label:'PnL / ROI', value:`${pnl >= 0 ? '<span class="good">+' : '<span class="bad">'}${fmtMoney(pnl)}</span>  (${roi >= 0 ? '+' : ''}${fmtPct(roi)})`},
    {label:'Open positions', value:`${s.open_positions}`},
    {label:'Closed trades', value:`${s.closed_trades}`},
    {label:'Wins / Losses', value:`${s.wins} / ${s.losses}`},
    {label:'Entry cost', value:`${fmtPct(p.entry_cost_rate)}`},
  ];

  kpis.innerHTML = '';
  boxes.forEach(b => {
    const box = document.createElement('div');
    box.className = 'box';
    box.innerHTML = `<div class="value">${b.value}</div><div class="label">${b.label}</div>`;
    kpis.appendChild(box);
  });
}

function renderExposure(p){
  const s = p.stats;
  const total = s.exposure_total || 0;
  const byCluster = s.exposure_by_cluster || {};

  let html = `<div><b>Exposure total:</b> ${fmtMoney(total)}</div>`;
  const items = Object.entries(byCluster);
  if (items.length) {
    html += '<div style="height:6px"></div><div><b>By cluster:</b></div>';
    html += '<ul style="margin:6px 0 0 18px; padding:0">';
    items.slice(0, 10).forEach(([k, v]) => {
      html += `<li><span class="pill">${k}</span>  ${fmtMoney(v)}</li>`;
    });
    html += '</ul>';
  }
  byId('exposure').innerHTML = html;
}

function renderOpenTable(p, query){
  const table = byId('open_table');
  const rows = p.open_positions || [];

  const q = (query || '').trim().toLowerCase();
  const filtered = q ? rows.filter(r => {
    return String(r.question || '').toLowerCase().includes(q)
      || String(r.cluster || '').toLowerCase().includes(q)
      || String(r.expected_close || '').toLowerCase().includes(q)
      || String(r.bet_side || '').toLowerCase().includes(q);
  }) : rows;

  byId('open_meta').innerText = `${filtered.length} shown / ${rows.length} total`;

  let html = '<thead><tr>';
  html += '<th>Market</th><th>Side</th><th>Entry</th><th>Size</th><th>Close</th><th>Cluster</th>';
  html += '</tr></thead><tbody>';

  filtered.slice(0, 250).forEach(r => {
    const url = r.url || '';
    const title = r.question || '(no question)';
    const mid = r.market_id || '';
    const entry = r.entry_price !== null ? fmtPct(r.entry_price) : '-';
    const size = r.size_usd !== null ? fmtMoney(r.size_usd) : '-';
    const close = r.expected_close || '-';
    const cluster = r.cluster || 'other';
    const side = r.bet_side || '-';

    const marketCell = url ? `<a href="${url}" target="_blank" rel="noopener">${title}</a><div class="muted mono">id: ${mid}</div>`
                           : `${title}<div class="muted mono">id: ${mid}</div>`;

    html += `<tr>`;
    html += `<td>${marketCell}</td>`;
    html += `<td><span class="pill">${side}</span></td>`;
    html += `<td>${entry}</td>`;
    html += `<td>${size}</td>`;
    html += `<td>${close}</td>`;
    html += `<td><span class="pill">${cluster}</span></td>`;
    html += `</tr>`;
  });

  html += '</tbody>';
  table.innerHTML = html;
}

function renderClosedTable(p){
  const table = byId('closed_table');
  const rows = p.recent_closed || [];

  let html = '<thead><tr>';
  html += '<th>Market</th><th>Resolution</th><th>PnL</th><th>Close</th>';
  html += '</tr></thead><tbody>';

  rows.slice(0, 30).forEach(r => {
    const url = r.url || '';
    const title = r.question || '(no question)';
    const mid = r.market_id || '';
    const resolution = r.resolution === null || r.resolution === undefined ? '-' : String(r.resolution);
    const pnl = r.pnl;
    const pnlStr = pnl === null || pnl === undefined ? '-' : `${pnl >= 0 ? '<span class="good">+' : '<span class="bad">'}${fmtMoney(pnl)}</span>`;
    const close = r.close_date || '-';

    const marketCell = url ? `<a href="${url}" target="_blank" rel="noopener">${title}</a><div class="muted mono">id: ${mid}</div>`
                           : `${title}<div class="muted mono">id: ${mid}</div>`;

    html += `<tr>`;
    html += `<td>${marketCell}</td>`;
    html += `<td>${resolution}</td>`;
    html += `<td>${pnlStr}</td>`;
    html += `<td>${close}</td>`;
    html += `</tr>`;
  });

  html += '</tbody>';
  table.innerHTML = html;
}

function renderMeta(){
  const generatedAt = DATA.generated_at || '-';
  byId('meta').innerHTML = `Generated: <span class="mono">${generatedAt}</span> (UTC)`;
}

function renderAll(){
  renderTabs();
  renderMeta();
  const p = DATA.portfolios[current];
  if (!p) return;

  renderKPIs(p);
  renderExposure(p);
  renderOpenTable(p, byId('search').value);
  renderClosedTable(p);
}

async function main(){
  const res = await fetch('./data.json', {cache: 'no-store'});
  DATA = await res.json();
  const names = Object.keys(DATA.portfolios);
  current = names[0] || null;
  byId('search').addEventListener('input', () => renderOpenTable(DATA.portfolios[current], byId('search').value));
  renderAll();
}

main();
</script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="site", help="Output folder (default: site)")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = build_data()

    with open(out_dir / "data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(out_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(render_html())

    print(f"Dashboard written to: {out_dir}/index.html")


if __name__ == "__main__":
    main()
