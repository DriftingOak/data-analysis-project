#!/usr/bin/env python3
"""
Quick text report - run locally anytime:
    python generate_report.py
"""

import json
import glob
from datetime import datetime

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"{'='*65}")
    lines.append(f"  POLYMARKET PAPER TRADING REPORT  —  {now}")
    lines.append(f"{'='*65}\n")

    portfolios = sorted(glob.glob("portfolio_*.json"))
    portfolios = [p for p in portfolios if "live" not in p]

    if not portfolios:
        lines.append("No portfolio files found.")
        print("\n".join(lines))
        return

    # ── Aggregate ──
    totals = {"realized": 0, "unrealized": 0, "wins": 0, "losses": 0, "open": 0}
    strat_rows = []

    for filepath in portfolios:
        strat_key = filepath.replace("portfolio_", "").replace(".json", "")
        try:
            with open(filepath) as f:
                data = json.load(f)
        except:
            continue

        meta = data.get("meta", {})
        name = meta.get("name", strat_key)
        bankroll_init = data.get("bankroll_initial", 1000)
        wins = data.get("wins", 0)
        losses = data.get("losses", 0)
        pnl = data.get("total_pnl", 0)

        open_pos = [p for p in data.get("positions", []) if p.get("status") == "open"]
        closed = data.get("closed_trades", [])

        # Realized P&L from closed trades
        realized = sum(t.get("pnl", 0) for t in closed)
        unrealized = pnl - realized if pnl else 0

        roi = (pnl / bankroll_init * 100) if bankroll_init > 0 else 0
        wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        totals["realized"] += realized
        totals["unrealized"] += unrealized
        totals["wins"] += wins
        totals["losses"] += losses
        totals["open"] += len(open_pos)

        strat_rows.append({
            "name": name,
            "key": strat_key,
            "realized": realized,
            "pnl": pnl,
            "roi": roi,
            "wr": wr,
            "wins": wins,
            "losses": losses,
            "open": len(open_pos),
            "positions": open_pos,
            "closed": closed,
        })

    # ── Summary ──
    total_pnl = totals["realized"] + totals["unrealized"]
    total_wr = (totals["wins"] / (totals["wins"] + totals["losses"]) * 100) if (totals["wins"] + totals["losses"]) > 0 else 0

    lines.append(f"  AGGREGATE")
    lines.append(f"  Total P&L:    ${total_pnl:+,.2f}  (Realized: ${totals['realized']:+,.2f})")
    lines.append(f"  Win Rate:     {total_wr:.0f}%  ({totals['wins']}W / {totals['losses']}L)")
    lines.append(f"  Open:         {totals['open']} positions across {len(strat_rows)} strategies")
    lines.append(f"\n{'─'*65}")

    # ── Strategy comparison ──
    lines.append(f"\n  {'Strategy':<22} {'P&L':>9} {'ROI':>8} {'WR':>6} {'W/L':>7} {'Open':>5}")
    lines.append(f"  {'─'*22} {'─'*9} {'─'*8} {'─'*6} {'─'*7} {'─'*5}")

    for s in sorted(strat_rows, key=lambda x: x["pnl"], reverse=True):
        lines.append(
            f"  {s['name']:<22} ${s['pnl']:>+7.0f} {s['roi']:>+7.1f}% {s['wr']:>5.0f}% "
            f"{s['wins']}W/{s['losses']}L {s['open']:>4}"
        )

    # ── Open positions detail (top strategies only) ──
    lines.append(f"\n{'─'*65}")
    lines.append(f"\n  OPEN POSITIONS (all strategies)")
    lines.append(f"  {'─'*60}")

    all_open = []
    for s in strat_rows:
        for pos in s["positions"]:
            pos["_strat"] = s["key"]
            all_open.append(pos)

    if all_open:
        for pos in sorted(all_open, key=lambda p: p.get("entry_date", "")):
            q = (pos.get("question", ""))[:50]
            side = pos.get("bet_side", "NO")
            entry = pos.get("entry_price", 0)
            size = pos.get("size_usd", 0)
            cluster = pos.get("cluster", "")
            date = (pos.get("entry_date", ""))[:10]
            strat = pos["_strat"]
            lines.append(f"  {side} @ {entry:.0%} | ${size:.0f} | {date} | {cluster}")
            lines.append(f"    {q}  [{strat}]")
    else:
        lines.append("  (none)")

    # ── Recent closed trades ──
    lines.append(f"\n{'─'*65}")
    lines.append(f"\n  RECENT CLOSED TRADES (last 15)")
    lines.append(f"  {'─'*60}")

    all_closed = []
    for s in strat_rows:
        for t in s["closed"]:
            t["_strat"] = s["key"]
            all_closed.append(t)

    recent = sorted(all_closed, key=lambda t: t.get("close_date", ""), reverse=True)[:15]
    if recent:
        for t in recent:
            emoji = "WIN " if t.get("resolution") == "win" else "LOSS"
            pnl = t.get("pnl", 0)
            q = (t.get("question", ""))[:45]
            date = (t.get("close_date", ""))[:10]
            lines.append(f"  {emoji} ${pnl:>+7.2f} | {date} | {q}")
    else:
        lines.append("  (none yet)")

    lines.append(f"\n{'='*65}\n")

    # ── Output ──
    report = "\n".join(lines)
    print(report)

    with open("report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OK] Saved to report.txt")


if __name__ == "__main__":
    main()
