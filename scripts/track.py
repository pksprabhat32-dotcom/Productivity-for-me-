#!/usr/bin/env python3
"""Compute goal status from goals.json + logs/log.md.

Usage:
    python3 scripts/track.py            # print report
    python3 scripts/track.py --build    # print report and regenerate dashboard/data.js
    python3 scripts/track.py --date 2026-10-01   # pretend today is that date
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOALS = ROOT / "goals.json"
LOG = ROOT / "logs" / "log.md"
DATA = ROOT / "dashboard" / "data.js"

# Tolerance before we call a goal "behind": you may be this far under the
# straight-line pace without it counting as slipping.
SLIP_TOLERANCE = 0.05

ENTRY = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([0-9.]+)\s*h?\s*(?:\|\s*(.*))?$"
)


def parse_date(s):
    y, m, d = (int(p) for p in s.split("-"))
    return date(y, m, d)


def load_entries():
    """Read logs/log.md. Only lines after the first '---' separator count."""
    if not LOG.exists():
        return [], []
    lines = LOG.read_text().splitlines()
    try:
        start = lines.index("---") + 1
    except ValueError:
        start = 0
    entries, bad = [], []
    for lineno, raw in enumerate(lines[start:], start=start + 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = ENTRY.match(line)
        if not m:
            bad.append((lineno, line))
            continue
        entries.append(
            {
                "date": parse_date(m.group(1)),
                "goal": m.group(2).strip(),
                "hours": float(m.group(3)),
                "note": (m.group(4) or "").strip(),
            }
        )
    return entries, bad


def streak(dates, today):
    """Consecutive days with a non-zero entry, ending today or yesterday."""
    days = set(dates)
    if today in days:
        cursor = today
    elif (today - timedelta(days=1)) in days:
        cursor = today - timedelta(days=1)
    else:
        return 0
    n = 0
    while cursor in days:
        n += 1
        cursor -= timedelta(days=1)
    return n


def assess(goal, entries, today):
    start = parse_date(goal["start"])
    deadline = parse_date(goal["deadline"])
    span = max((deadline - start).days, 1)
    elapsed = (today - start).days
    days_left = (deadline - today).days

    # Fraction of the calendar that has burned, clamped to [0, 1].
    time_frac = min(max(elapsed / span, 0.0), 1.0)

    ms = goal.get("milestones", [])
    done = [m for m in ms if m.get("done")]
    work_frac = (len(done) / len(ms)) if ms else 0.0

    mine = [e for e in entries if e["goal"] == goal["id"]]
    logged = sum(e["hours"] for e in mine)
    target_daily = float(goal.get("daily_hours") or 0)
    # Hours you should have banked by now, if you'd hit target every day so far.
    expected_hours = target_daily * max(elapsed, 0)
    worked_days = sorted({e["date"] for e in mine if e["hours"] > 0})

    if days_left < 0:
        state = "done" if work_frac >= 1.0 else "overdue"
    elif work_frac >= 1.0:
        state = "done"
    elif work_frac >= time_frac - SLIP_TOLERANCE:
        state = "on-track"
    elif work_frac >= time_frac - 0.20:
        state = "slipping"
    else:
        state = "behind"

    # What the remaining work costs per day from here on.
    remaining_ms = len(ms) - len(done)
    per_day_needed = None
    if days_left > 0 and expected_hours > 0:
        total_planned = target_daily * span
        per_day_needed = round(max(total_planned - logged, 0) / days_left, 2)

    overdue_ms = [
        m for m in ms if not m.get("done") and parse_date(m["due"]) < today
    ]
    upcoming = sorted(
        (m for m in ms if not m.get("done")), key=lambda m: m["due"]
    )

    return {
        "id": goal["id"],
        "title": goal["title"],
        "category": goal.get("category", ""),
        "why": goal.get("why", ""),
        "start": goal["start"],
        "deadline": goal["deadline"],
        "days_total": span,
        "days_elapsed": max(elapsed, 0),
        "days_left": days_left,
        "time_frac": round(time_frac, 4),
        "work_frac": round(work_frac, 4),
        "state": state,
        "milestones": ms,
        "milestones_done": len(done),
        "milestones_total": len(ms),
        "milestones_remaining": remaining_ms,
        "overdue_milestones": [m["title"] for m in overdue_ms],
        "next_milestone": upcoming[0] if upcoming else None,
        "daily_hours_target": target_daily,
        "hours_logged": round(logged, 2),
        "hours_expected": round(expected_hours, 2),
        "hours_debt": round(expected_hours - logged, 2),
        "per_day_needed": per_day_needed,
        "days_worked": len(worked_days),
        "streak": streak(worked_days, today),
        "last_worked": worked_days[-1].isoformat() if worked_days else None,
    }


BAR = 28


def bar(frac):
    filled = int(round(frac * BAR))
    return "#" * filled + "." * (BAR - filled)


LABEL = {
    "on-track": "ON TRACK",
    "slipping": "SLIPPING",
    "behind": "BEHIND",
    "overdue": "OVERDUE",
    "done": "DONE",
}


def report(results, today, bad):
    out = [f"GOAL TRACKER  —  {today.isoformat()}", "=" * 58, ""]
    if not results:
        out.append("No goals yet. Add them to goals.json.")
        return "\n".join(out)

    for r in results:
        out.append(f"{r['title']}  [{LABEL[r['state']]}]")
        out.append(f"  time  {bar(r['time_frac'])} {r['time_frac']*100:5.1f}%  ({r['days_left']} days left)")
        out.append(f"  work  {bar(r['work_frac'])} {r['work_frac']*100:5.1f}%  ({r['milestones_done']}/{r['milestones_total']} milestones)")
        debt = r["hours_debt"]
        if r["daily_hours_target"]:
            verdict = f"{abs(debt):.1f}h {'behind' if debt > 0 else 'ahead of'} plan"
            out.append(f"  hours {r['hours_logged']:.1f} logged vs {r['hours_expected']:.1f} expected — {verdict}")
            if r["per_day_needed"] is not None:
                out.append(f"  to finish on time: {r['per_day_needed']}h/day from here")
        out.append(f"  streak {r['streak']} day(s), worked {r['days_worked']} of {r['days_elapsed']} days")
        if r["overdue_milestones"]:
            out.append(f"  !! overdue: {', '.join(r['overdue_milestones'])}")
        if r["next_milestone"]:
            nm = r["next_milestone"]
            out.append(f"  next: {nm['title']} (due {nm['due']})")
        out.append("")

    if bad:
        out.append("Unparsed log lines (fix the format):")
        for lineno, line in bad:
            out.append(f"  line {lineno}: {line}")
        out.append("")
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    today = date.today()
    if "--date" in args:
        today = parse_date(args[args.index("--date") + 1])

    cfg = json.loads(GOALS.read_text())
    entries, bad = load_entries()
    results = [assess(g, entries, today) for g in cfg.get("goals", [])]
    # Worst first: the thing most at risk should be the thing you see first.
    order = {"overdue": 0, "behind": 1, "slipping": 2, "on-track": 3, "done": 4}
    results.sort(key=lambda r: (order[r["state"]], r["days_left"]))

    print(report(results, today, bad))

    if "--build" in args:
        recent = sorted(entries, key=lambda e: e["date"], reverse=True)[:14]
        payload = {
            "generated": today.isoformat(),
            "owner": cfg.get("owner", ""),
            "goals": results,
            "recent": [
                {
                    "date": e["date"].isoformat(),
                    "goal": e["goal"],
                    "hours": e["hours"],
                    "note": e["note"],
                }
                for e in recent
            ],
        }
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(
            "window.TRACKER_DATA = " + json.dumps(payload, indent=2) + ";\n"
        )
        print(f"wrote {DATA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
