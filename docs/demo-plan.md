# Strompilot demo plan

Six-minute judge demo of the agent-first power copilot. English UI,
Berlin household, live day-ahead prices.

## Setup (5 minutes before)

1. Start the backend: `cd api; ..\.venv\Scripts\python.exe -m uvicorn
   strompilot.main:app --host 127.0.0.1 --port 8000`.
2. Start the web app: `cd web; npm run start -- --port 3100`.
3. Confirm both answer: `/health` returns 200, `/` renders.
4. Open Chrome with translate off and these tabs:
   - http://127.0.0.1:3100/ (Prices)
   - http://127.0.0.1:3100/plan?thread=fcf0f931616849b1baec8382ada7bd75
     (seeded approved plan, the fallback if live planning stalls)
   - http://127.0.0.1:3100/meter
   - http://127.0.0.1:3100/alarms
   - http://127.0.0.1:3100/about
   - http://127.0.0.1:3100/household
5. Keep the seed script ready, not run: `scripts/seed_demo.py` rebuilds
   the showcase case in about two minutes if the database is ever
   wiped mid-demo.

## Script

### 0:00 The hook (30 seconds)

"German households on dynamic tariffs get a new price every hour and
no help using it. Strompilot turns one sentence of daily life into an
optimal, explained power plan." Show the Prices heatmap and the price
hero. Point at the cheapest hour.

### 0:30 The live plan (2 minutes)

Type in Make a plan: "Night shift, baby sleeps by 10 pm, car must be
full by 07:00". Submit. While the agents run, narrate the live trace:
perceive, analyze, schedule, explain, critic. When it pauses, open one
schedule block: every number carries its formula and source. Approve
it, then give feedback: "The next plan learns from this."

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
numbers: 456 backend tests, 39 frontend tests, 10 browser journeys,
20 of 20 live evals passing.

### 5:30 The close (30 seconds)

"Deterministic optimizer, glass-box numbers, human approval, memory
that learns. Private by default: local SQLite, photos in memory
unless you agree, personal data stripped before every model call."

## Judge questions crib

- Models: Muse Spark 1.3 reasons on Meta, Spark Open writes volume
  on Baseten with per-call fallback, Wonder reviews critically, SAM
  3.1 finds the display, Image paints the report cover. Full register
  in docs/model-usage.md.
- Why agents: the graph pauses for approval and vetoes weak drafts;
  the optimizer itself is deterministic, never the model guessing.
- Data honesty: hourly feed while tariffs settle quarter-hourly,
  standard-profile estimates, grid fees and holidays approximated.
  Every caveat is printed in the UI, not hidden.
- Auth: the demo runs one fixed household. Login and per-user data
  are the next tracked issue, openly, not silently missing.
