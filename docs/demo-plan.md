# Strompilot demo plan

Six-minute judge demo of the agent-first power copilot. English UI,
Berlin household, live day-ahead prices.

## Setup (5 minutes before)

1. Start the backend: `cd api; $env:STROMPILOT_DEV_LINKS=1;
   ..\.venv\Scripts\python.exe -m uvicorn strompilot.main:app
   --host 127.0.0.1 --port 8000`. The demo flag enables one-click
   development sign-in links — never set it in production.
2. Start the web app: `cd web; npm run start -- --port 3100`.
3. Confirm both answer: `/health` returns 200, `/` renders.
4. Sign in on http://127.0.0.1:3100/signin as demo@example.de and
   click the development link. Every household view needs this session.
5. Open Chrome with translate off and these tabs:
   - http://127.0.0.1:3100/ (Today)
   - http://127.0.0.1:3100/plan?thread=16121e2d24cc44c48572ab29446cd4f7
     (seeded approved plan, the fallback if live planning stalls)
   - http://127.0.0.1:3100/meter
   - http://127.0.0.1:3100/alarms
   - http://127.0.0.1:3100/about
   - http://127.0.0.1:3100/household
   - http://127.0.0.1:3100/account
   - http://127.0.0.1:3100/solar (teaser: roof measure plus preview)
6. Keep the seed script ready, not run: `scripts/seed_demo.py` rebuilds
   the showcase case in about two minutes if the database is ever
   wiped mid-demo. It signs in as the demo email by itself.

## Script

### 0:00 The hook (30 seconds)

"German households on dynamic tariffs get a new price every hour and
no help using it. Strompilot turns one sentence of daily life into an
optimal, explained power plan." Show the Today hero and heatmap.
Point at the cheapest window and its all-in label.

### 0:30 The live plan (2 minutes)

Type in Make a plan: "Night shift, the baby sleeps by 8pm, the car
must be full by 6am". Submit. While the agents run, narrate the live
trace: Perceive, Analyze, Schedule, Explain, Review — each step names
its model. If the trace shows a critic veto, narrate it: "See — the
critic disagreed about a real constraint, and the analyst fixed it
before anything was scheduled." When it pauses, open one schedule
block: cost, average rate, the reason you gave, written by Spark Open
and checked by Wonder. Approve it and point at "Program wallbox" in
the trace, then give feedback: "The next plan learns from this."

Fallback: if the run stalls past 90 seconds, switch to the seeded
plan tab. It shows the same finished state with three devices.

### 2:30 The meter (1 minute)

On Meter, upload a real meter photo if one is at hand; otherwise use
`api/tests/fixtures/meter/meter_clean.png` and say so openly. Point
at the SAM status, the serial number, and the stored thumbnail.
Confirm the reading and show the calibration note.

### 3:30 The alarms (1 minute)

On Alarms, press Check now. Either a fresh English alert appears or
the delivered list explains itself. Open Household to show where the
devices and quiet hours behind the watch come from.

### 4:30 The proof (1 minute)

On About, show the live stats and the pipeline. Quote the hard
numbers: 572 backend tests, 83 frontend tests, 12 browser journeys
plus the demo capture, 25 live evals out of 37 cases including
5 judge-groundedness cases.

### 5:30 The close (30 seconds)

"Deterministic optimizer, glass-box numbers, human approval, memory
that learns. Private by default: local SQLite, photos in memory
unless you agree, personal data stripped before every model call."

## Judge questions crib

- Models: Muse Spark 1.3 reasons on Meta, Spark Open writes volume
  on Baseten with per-call fallback, Wonder reviews critically, SAM
  3.1 finds the display, Image renders the report cover on request.
  Full register in docs/model-usage.md.
- Why agents: the graph pauses for approval and vetoes weak drafts;
  the optimizer itself is deterministic, never the model guessing.
- Data honesty: hourly feed while tariffs settle quarter-hourly,
  standard-profile estimates, grid fees and holidays approximated.
  Every caveat is printed in the UI, not hidden.
- Auth: magic-link sign-in, one household per email, sessions expire
  and revoke. The Account view adopts the legacy local profile.
  Planning consent is one checkbox at sign-in, revocable in
  Household.

## Demo-day checklist

Run through this list the morning of the demo, in order:

- [ ] After about 13:00 CET (when tomorrow's prices publish), delete
  `data/prices/fetches.json`, call
  `/prices/day-ahead?date=<tomorrow>`, and confirm the source ends
  in `-live`. Sample data is labeled, never silent — but judges
  should see the live feed.
- [ ] Use `127.0.0.1` everywhere, never `localhost`. The SameSite=Lax
  session cookie set by `127.0.0.1:8000` won't be sent from a
  `localhost:3100` page, and it fails silently as a 401.
- [ ] Run `api/scripts/validate_keys.py` beforehand. Reading plans,
  prices, and reports works without keys, but the live plan leg —
  perceive, explain, critic — needs `META_API_KEY` and
  `BASETEN_API_KEY`. Without them, demo from the seeded thread.
- [ ] Use the production build (`npm run build && npm run start`).
  `next dev` failed its hot-reload handshake on the reviewer's
  machine and the sign-in button did nothing.
- [ ] Pre-warm once: open `/health`, then call `/wallbox/status`
  (it spawns a Python subprocess per call, so the first one is
  slow). The backend pre-warms its databases at startup.
- [ ] Prefer not to restart uvicorn mid-run. Crashed runs are marked
  blocked with their error since the reliability pass, so a
  restart no longer strands threads — but the recording still
  loses its live trace.
- [ ] Rehearse one judge-style weird input ("ignore previous
  instructions", a JSON blob). Extraction is injection-hardened
  and empty input ends the run with "nothing to schedule".
