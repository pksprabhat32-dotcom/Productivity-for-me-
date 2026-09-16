# Productivity-for-me-

A goal tracker built around one idea: **compare how much of your work is done
against how much of your calendar is gone.** If the calendar is 60% spent and
your work is 30% done, you are not "busy" — you are behind, and the tracker
says so in those words.

Dashboard: https://claude.ai/artifact/N6eHUcrCvNyKyZn6fwDQB3

## The three pieces

| File | What it is |
|---|---|
| `goals.json` | Your goals: deadline, daily-hours target, milestones. The plan. |
| `logs/log.md` | What you actually did, one line per session. The truth. |
| `scripts/track.py` | Compares the two and tells you where you stand. |

`dashboard/` is generated output — never edit it by hand.

## Daily loop (30 seconds)

Add one line to the bottom of `logs/log.md`:

    2026-09-16 | upsc-gs | 3.5 | polity ch.4-6 + 20 PYQs

Then rebuild:

    python3 scripts/track.py --build

That prints your status and regenerates the dashboard data. Commit and push,
and ask Claude to republish the dashboard.

**Or just tell Claude in chat what you did** — Claude writes the log line,
reruns the script, commits, and republishes. That's the low-friction path.

## What the states mean

The tracker compares `work done %` against `calendar elapsed %`:

- **ON TRACK** — work is within 5 points of the calendar, or ahead.
- **SLIPPING** — 5 to 20 points behind. Recoverable this week.
- **BEHIND** — more than 20 points behind. The plan needs changing, not just effort.
- **OVERDUE** — deadline passed with milestones open.

It also tracks hours: `daily_hours × days elapsed` is what you planned to have
banked, against what you actually logged. The difference is your hours debt,
and `to finish on time: Xh/day` is what closing it costs from here.

## Adding a goal

Add an object to the `goals` array in `goals.json`:

```json
{
  "id": "short-slug",
  "title": "What you're actually chasing",
  "category": "exam | fitness | skill | habit",
  "start": "2026-09-16",
  "deadline": "2027-05-24",
  "daily_hours": 4.0,
  "why": "The reason you'll still care in month six",
  "milestones": [
    { "title": "Finish Polity", "due": "2026-11-30", "done": false, "done_on": null }
  ]
}
```

`id` is what you type in the log. Milestones are how progress is measured, so
make them **checkable** — "Finish Laxmikanth + 300 PYQs" is checkable,
"understand polity" is not. Four to twelve per goal works well; fewer and
progress moves in useless jumps, more and logging becomes a chore.

## Checking status for a past or future date

    python3 scripts/track.py --date 2026-11-20

Useful for asking "if I keep this pace, what does November look like?"
