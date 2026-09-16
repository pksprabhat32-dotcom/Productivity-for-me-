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

# Mon=0 .. Sun=6, matching date.weekday(). A goal with no "active_days" set
# is assumed to run every day of the week (old behaviour, unchanged).
WEEKDAY_CODES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
ALL_DAYS = set(WEEKDAY_CODES)


def active_set(goal):
    days = goal.get("active_days")
    return set(days) if days else set(ALL_DAYS)


def is_active(d, days_set):
    return WEEKDAY_CODES[d.weekday()] in days_set


def count_active_days(d0, d1, days_set):
    """Active days in the half-open range [d0, d1). Days before d0 count 0."""
    n = (d1 - d0).days
    if n <= 0:
        return 0
    if days_set == ALL_DAYS:
        return n
    return sum(1 for i in range(n) if is_active(d0 + timedelta(days=i), days_set))

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


def streak(dates, today, days_set=None):
    """Consecutive worked active-days, ending today or yesterday.

    A rest day (Sunday on a 6-day-week goal) is skipped, not a break — the
    streak shouldn't reset just because Sunday isn't a work day for this goal.
    """
    days_set = days_set or ALL_DAYS
    worked = set(dates)

    cursor = today
    if is_active(cursor, days_set) and cursor not in worked:
        # Grace for today: it may simply not be logged yet.
        cursor -= timedelta(days=1)

    n = 0
    limit = 3660  # ~10 years back, just a sane backstop against a bad config
    for _ in range(limit):
        if not is_active(cursor, days_set):
            cursor -= timedelta(days=1)
            continue
        if cursor in worked:
            n += 1
            cursor -= timedelta(days=1)
        else:
            break
    return n


def assess(goal, entries, today):
    start = parse_date(goal["start"])
    deadline = parse_date(goal["deadline"])
    days_set = active_set(goal)

    span = max((deadline - start).days, 1)
    elapsed = (today - start).days
    days_left = (deadline - today).days  # calendar days, for the countdown display

    # Work-day equivalents of the same three spans, so a goal with Sundays off
    # isn't judged "behind" for skipping a day it was never meant to work.
    active_span = count_active_days(start, deadline, days_set) or span
    active_elapsed = count_active_days(start, today, days_set)
    active_days_left = count_active_days(today, deadline, days_set)

    # Fraction of the *working* calendar that has burned, clamped to [0, 1].
    time_frac = min(max(active_elapsed / active_span, 0.0), 1.0)

    ms = goal.get("milestones", [])
    done = [m for m in ms if m.get("done")]
    work_frac = (len(done) / len(ms)) if ms else 0.0

    mine = [e for e in entries if e["goal"] == goal["id"]]
    logged = sum(e["hours"] for e in mine)
    target_daily = float(goal.get("daily_hours") or 0)
    # Hours you should have banked by now, at target on every active day so far.
    expected_hours = target_daily * max(active_elapsed, 0)
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

    # What the remaining work costs per *active* day from here on.
    remaining_ms = len(ms) - len(done)
    per_day_needed = None
    if active_days_left > 0 and expected_hours > 0:
        total_planned = target_daily * active_span
        per_day_needed = round(max(total_planned - logged, 0) / active_days_left, 2)

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
        "active_days": sorted(days_set, key=WEEKDAY_CODES.index),
        "days_total": span,
        "days_elapsed": max(elapsed, 0),
        "days_left": days_left,
        "active_days_left": active_days_left,
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
        "streak": streak(worked_days, today, days_set),
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
        try:
            import today as today_mod  # noqa: WPS433 - optional companion module
            brief = today_mod.build(today)
        except Exception:
            brief = None

        payload = {
            "generated": today.isoformat(),
            "brief": brief,
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
