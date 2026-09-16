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

## Getting today's goal

    python3 scripts/today.py --write

Turns the plan into one concrete assignment: hours to put in, which milestone
you're aiming at, and which specific pieces to do today. It writes `TODAY.md`
and appears at the top of the dashboard.

How the assignment is derived:

- **Hours** = your `daily_hours`, raised to the catch-up rate if you're carrying
  debt, capped at 14h. Above that cap it stops raising the number and tells you
  the plan is broken instead — effort can't fix a deadline that's already gone.
- **Pieces** = remaining `chunks` of the next milestone, divided by days left
  until it's due, rounded up.

Chunks are optional but they're what makes a daily goal specific. Without them
the brief can only say "put in 4 hours". With them it says exactly what to open:

```json
{
  "title": "Finish Polity",
  "due": "2026-11-30",
  "done": false,
  "done_on": null,
  "chunks": [
    { "t": "Laxmikanth ch.1-5", "done": true },
    { "t": "Laxmikanth ch.6-10", "done": false }
  ]
}
```

## Real plan (as of Sep 2026)

Seven goals, replacing the sample:

| Goal | Window | Days | Hours/day |
|---|---|---|---|
| `gs-completion` | now → 20 Jan 2027 | Mon–Sat | 5.0 |
| `psir-foundation` | now → 20 Jan 2027 | Mon–Sat | 4.0 |
| `yt-foundation` | now → 20 Jan 2027 | Mon–Sat | 6.0 |
| `gs-revision` | 20 Jan → 16 May 2027 | Mon–Sat | 5.0 |
| `psir-revision` | 20 Jan → 16 May 2027 | Mon–Sat | 4.0 |
| `yt-growth` | 20 Jan → 16 May 2027 | Mon–Sat | 6.0 |
| `current-affairs` | now → 16 May 2027 | **Sunday only** | 6.0 |

Prelims target: 16 May 2027 (a Sunday, matching UPSC's usual pattern).
Already covered before this plan started: Geography, Environment (basic),
Ancient & Medieval History, Polity — not re-taught, but folded into the
revision-phase milestones so they get a recall pass too. PSIR is being built
from zero.

### Why a goal has an `active_days` field

Sunday is current-affairs + personal time, not a rest day from the tracker's
point of view — but it's also not a work day for the six-day-week goals. Each
goal in `goals.json` can carry `"active_days": ["mon", ..., "sat"]`; the pace
math (`time_frac`, `hours_expected`, `per_day_needed`, streaks) only counts a
goal's own active days, so Sunday never shows up as a missed day for
`gs-completion` and Mon–Sat never counts against `current-affairs`. A goal
with no `active_days` runs every day, unchanged from before.

`scripts/today.py` uses the same field to decide what's even on the table
today — on a Sunday it shows only `current-affairs`; the rest say so under
"Off today (not scheduled)" instead of asking for hours they were never due.
