#!/usr/bin/env python3
"""Turn the plan in goals.json into one concrete assignment for today.

Usage:
    python3 scripts/today.py               # print today's brief
    python3 scripts/today.py --write       # also write TODAY.md
    python3 scripts/today.py --date 2026-10-01
"""

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from track import GOALS, LOG, ROOT, assess, load_entries, parse_date  # noqa: E402

TODAY_MD = ROOT / "TODAY.md"

# Never hand out a day that can't be worked. If the maths demands more than
# this, the plan is broken and the brief says so instead of pretending.
MAX_SANE_HOURS = 14.0


def round_quarter(h):
    return round(h * 4) / 4


def assignment(goal_result, today):
    """What this one goal needs from you today."""
    nm = goal_result["next_milestone"]
    target = goal_result["daily_hours_target"]

    # Catch-up rate wins when you're in debt, but only up to what a day holds.
    hours = max(target, goal_result["per_day_needed"] or 0)
    impossible = hours > MAX_SANE_HOURS
    hours = round_quarter(min(hours, MAX_SANE_HOURS))

    out = {
        "id": goal_result["id"],
        "title": goal_result["title"],
        "state": goal_result["state"],
        "hours": hours,
        "impossible": impossible,
        "milestone": None,
        "due_in": None,
        "chunks": [],
        "chunks_left": 0,
        "note": "",
    }
    if goal_result["state"] == "done":
        out["note"] = "Finished. Nothing due."
        out["hours"] = 0
        return out
    if not nm:
        out["note"] = "No milestones left to aim at — add the next ones."
        return out

    due = parse_date(nm["due"])
    days_to = (due - today).days
    out["milestone"] = nm["title"]
    out["due_in"] = days_to

    chunks = nm.get("chunks") or []
    undone = [c for c in chunks if not c.get("done")]
    out["chunks_left"] = len(undone)

    if undone:
        # Spread what's left across the days left, rounding up so the last day
        # isn't carrying the whole remainder.
        per_day = math.ceil(len(undone) / max(days_to, 1))
        out["chunks"] = [c["t"] for c in undone[:per_day]]

    notes = []
    if days_to < 0:
        notes.append(f"Overdue by {abs(days_to)} days. Clear it before starting anything new.")
    elif days_to == 0:
        notes.append("Due today. This is the whole day's work.")
    if impossible:
        notes.append(
            f"The catch-up rate is now above {MAX_SANE_HOURS:g}h/day. "
            "Effort won't fix this — move the deadline or cut scope."
        )
    elif goal_result["hours_debt"] > 0 and days_to > 0:
        notes.append(
            f"Carrying {goal_result['hours_debt']:.1f}h of debt — today's target is raised to absorb it."
        )
    out["note"] = " ".join(notes)
    return out


def build(today):
    cfg = json.loads(GOALS.read_text())
    entries, _ = load_entries()
    results = [assess(g, entries, today) for g in cfg.get("goals", [])]

    order = {"overdue": 0, "behind": 1, "slipping": 2, "on-track": 3, "done": 4}
    results.sort(key=lambda r: (order[r["state"]], r["days_left"]))

    live = [r for r in results if r["state"] != "done"]
    tasks = [assignment(r, today) for r in live]

    yesterday = today - timedelta(days=1)
    logged_yday = any(e["date"] == yesterday for e in entries)
    logged_today = any(e["date"] == today for e in entries)
    nearest = min((r["days_left"] for r in live), default=None)

    return {
        "date": today.isoformat(),
        "weekday": today.strftime("%A"),
        "total_hours": round_quarter(sum(t["hours"] for t in tasks)),
        "tasks": tasks,
        "logged_yesterday": logged_yday,
        "logged_today": logged_today,
        "nearest_deadline": nearest,
        "streak": max((r["streak"] for r in results), default=0),
    }


def render(b):
    L = [f"# Today — {b['weekday']}, {b['date']}", ""]
    if b["nearest_deadline"] is not None:
        L.append(f"**{b['nearest_deadline']} days** to your nearest deadline. Streak: **{b['streak']}**.")
        L.append("")

    if not b["tasks"]:
        L.append("No active goals. Add them to `goals.json`.")
        return "\n".join(L)

    L.append(f"## The ask: {b['total_hours']}h total")
    L.append("")
    for t in b["tasks"]:
        L.append(f"### {t['title']} — {t['hours']}h")
        if t["milestone"]:
            when = (
                f"overdue by {abs(t['due_in'])}d" if t["due_in"] < 0
                else "due today" if t["due_in"] == 0
                else f"{t['due_in']} days left"
            )
            L.append(f"Aiming at: **{t['milestone']}** ({when}, {t['chunks_left']} pieces to go)")
        if t["chunks"]:
            L.append("")
            for c in t["chunks"]:
                L.append(f"- [ ] {c}")
        if t["note"]:
            L.append("")
            L.append(f"> {t['note']}")
        L.append("")

    L.append("## Log it when you're done")
    L.append("")
    L.append("```")
    for t in b["tasks"]:
        L.append(f"{b['date']} | {t['id']} | <hours> | <what you did>")
    L.append("```")
    if not b["logged_yesterday"]:
        L.append("")
        L.append("> Yesterday has no entry. Log a zero with the reason if it was a rest day —")
        L.append("> a blank day makes the pace maths lie.")
    return "\n".join(L)


def main():
    args = sys.argv[1:]
    today = date.today()
    if "--date" in args:
        today = parse_date(args[args.index("--date") + 1])

    brief = build(today)
    text = render(brief)
    print(text)

    if "--write" in args:
        TODAY_MD.write_text(text + "\n")
        print(f"\nwrote {TODAY_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
