# Project-Plan — Strompilot

We are building Strompilot as a solo Indie project. Every AI call goes to Meta
models only. The agent core runs on Python with FastAPI, using LangGraph, which
is a framework for building agents as graphs of steps. The user interface is
built with Next.js, React, and TypeScript, in German first with an English
toggle. Household data persists in SQLite, and rule lookup uses BM25, which is
a keyword search method that needs no AI model at all. Vector search is out
because Meta offers no embedding model.
We have ample time, so this plan optimizes for depth, not deadlines. The
separate hackathon event plan still tracks the November 4 submission window in
case the entry goes ahead.
Our thesis is simple: we build what could not be built before AI. Strompilot is
an agent household manager that understands everyday language, plans optimally,
explains itself, learns from feedback, and acts on its own initiative.

## Goal

We will ship Strompilot as an agent-first web app. A German household describes
its life in free text and receives an optimal, explained, self-updating power
plan based on live day-ahead prices. The app re-plans from meter photos, sends
Flex-Alarm alerts based on judgment rather than fixed thresholds, and improves
every plan through a learning loop. There are no forms to fill in, no settings
maze to navigate, and no smart meter required.

## Success Criteria

- The full loop works live in one app: everyday language becomes a plan, the
  plan comes with a cited explanation, alerts go out, feedback comes back, and
  future plans get better. Every step is powered by Meta models.
- We prove Meta-only compliance with an endpoint audit before we finish.
- Every issue below delivers a working and tested increment, and the full test
  suite is green.
- The project is demo-ready with a public repository and a three-minute video
  that shows only work built for this project.
- Every regulatory mapping in this plan is implemented and labeled in the UI.

## Target market

Our primary market is German households who buy power on dynamic tariffs or
are thinking about switching to one. Inside that group, the sweet spot is homes
with loads they can shift in time: an electric car with a wallbox, a heat pump,
a home battery, or even just a washer and dryer. Our second audience is
households without a smart meter, which is still roughly 95 percent of German
homes, because our standard-profile mode serves exactly them. We deliberately
do not target energy suppliers, grid operators, or non-German markets in this
plan.

## The AI-native core (impossible before AI)

1. **Life-to-plan.** The household writes one or two sentences about its daily
   life, and the app turns them into hard constraints, an optimal schedule, and
   a narration. No form could ever capture "the baby sleeps from 8pm", so this
   is our hero demo beat.
2. **A real agent, not a pipeline.** A goal-driven loop observes the situation,
   picks tools, and decides when it is done. Specialists for prices, scheduling,
   explanation, and critical review coordinate on a graph. Fixed playbooks break
   on anything new, but this loop handles novelty by design.
3. **Judgment-based alerting.** The household can say "only wake me if it is
   really worth it", and the agent decides what deserves an interruption from
   prices and memory. There are no fixed thresholds to configure.
4. **Living memory.** The agent learns preferences from conversation, recalls
   them across sessions, and forgets them on demand. This replaces the settings
   page that nobody ever opens.
5. **Learning loop.** Thumbs up and thumbs down on plans refine future plans,
   and the improvement is measured. Traditional software never gets better with
   use, but this agent does.
6. **A wallbox the agent drives.** A simulated wallbox runs as its own program
   outside our app, and the agent starts and stops charging through a standard
   plug called MCP. Watching the agent charge the car when prices drop is the
   visible proof of autonomy, and the simulator can later be swapped for real
   hardware without touching the agent.
7. **Self-updating plans plus cited trust.** Price changes, meter photos, and
   edited preferences trigger fresh plans with visible diffs. Every
   recommendation answers "why" with retrieved tariff rules and its exact
   reasoning trace, so nobody has to trust a black box.

## Choices: what we use, what we cut, and why

We use each of the following because it earns its place:
- A LangGraph multi-agent graph with a supervisor and four workers (analyst,
  scheduler, explainer, critic). It enforces order, branching, and human
  approval, and it is the centerpiece of the whole system. (Key-Concepts §13,
  §15, §18.)
- Retrieval as a tool the agent controls, with query rewriting and re-ranking,
  instead of a fixed retrieval pipe. (Key-Concepts §13.)
- Structured output with Pydantic schemas, because life-to-plan lives or dies
  on reliable extraction. (Key-Concepts §4, §6.)
- Few-shot examples, step-by-step reasoning, a clear persona, and a fallback
  answer for uncertain cases, which together carry narration quality.
  (Key-Concepts §3.)
- BM25 keyword search with LLM re-ranking and citations. It needs no AI model,
  so it keeps us Meta-compliant, and keywords beat vectors on tariff codes like
  §41a. (Key-Concepts §9.)
- Two small SQLite databases: one for conversation threads, one for lasting
  memories. (Key-Concepts §16.)
- A learning loop that turns feedback into preferences and tracks improvement.
  (Key-Concepts §13, §16.)
- Human approval interrupts before publishing plans, confirming meter readings,
  and running wallbox actions. This doubles as regulatory honesty.
  (Key-Concepts §16.)
- Simple guards: iteration caps, a pause after repeated identical calls,
  personal-data stripping, a cost rail, and an audit log. (Key-Concepts §14,
  §17.)
- A trace replay overlay, so observability is a feature and not plumbing.
  (Key-Concepts §8, §17.)
- A full evaluation suite with a dataset, prompt comparisons, cross-model
  judges, and red-team injection tests. (Key-Concepts §8.)
- Next.js with React and TypeScript for the frontend and FastAPI with LangGraph
  for the Python backend. This pairing gives us a winner-grade custom UI with
  a Python agent core, and Next.js is the course's own JavaScript-track
  alternative. (Key-Concepts §6.)
- uv, Ruff, python-dotenv, and TypeScript tooling, so both sides stay typed
  and clean. (Key-Concepts §6.)

We cut the following deliberately, even with ample time:
- Vector databases and embeddings, because they are impossible under the
  Meta-only constraint. (Key-Concepts §10.)
- Publishing our own tools as a public MCP server, which stays an optional
  extra because it serves distribution rather than the household.
  (Key-Concepts §12.)
- LangSmith, because it is commercial and our trace overlay plus evaluations
  cover the need. (Key-Concepts §8.)
- A full middleware framework and memory-type ceremony, because the same
  behaviors survive as simple code.
- Agent logic outside Python, because TypeScript owns rendering only while
  the agent core stays in Python.

## Architecture

The browser runs the Next.js "Leitstand" with five views (prices, schedule,
meter, alarms, about), a memory sidebar, and a "why" overlay. It talks to the
Python backend over REST plus live event streams, using one typed contract. The
backend runs a LangGraph supervisor graph with four workers that share typed
state and two SQLite databases. Eight tools cover prices, baselines,
optimization, explanation, meter intake, alerts, memory, and rule lookup.
Guards wrap everything, and feedback flows back into preferences. The primary
model leg calls Muse Spark 1.3 on Meta's endpoint, and the second leg calls
Muse Spark Open on Baseten. Beside the app, the wallbox simulator runs as its
own MCP server process, which the agent drives like a real device driver.

```
Browser: Next.js "Leitstand" ── Preise │ Fahrplan │ Zähler │ Alarme │ Über
  │  Warum-overlay + glass-box drawer + 👍/👎 (live streams)
  ▼  REST + streams ── typed contract
FastAPI `strompilot/` API (Python):
Supervisor graph: perceive → delegate → review → publish
  workers: price-analyst │ scheduler │ explainer │ critic
  shared: typed state + threads.db + memory.db
  tools: prices, baseline, optimize, explain, meter, alerts, memory, rules
  guards: approvals, data stripping, cost rail, loop pause, audit log
  learning: feedback → preferences → measured improvement
Models: Meta muse-spark-1.3 (primary) │ Baseten spark-open-1026 (second leg)
Deterministic core: price cache, H0 engine, tariff math, BM25, evals

Beside the app: wallbox simulator (own MCP server process)
  tools: start_charge, stop_charge, set_limit │ resource: live status
  agent drives it; UI animates it; big actions need approval
```

## Features

Core features:
- Life-to-plan intake turns free text into a household with editable
  constraints.
- Live 24-hour German day-ahead prices come from a cached feed with a fallback
  source and a clearly labeled sample mode.
- The multi-agent day planner produces schedules that pass a critic review
  gate.
- Device schedules for heat pump, wallbox, washer, and battery are priced in
  euros.
- German explanations cite tariff rules, every block replays its reasoning,
  and the live agent trace streams into the UI.
- Thumbs up and down visibly improve future plans through the learning loop.
- Flex-Alarm uses judgment and quiet hours, delivered in-app plus email or push.
- Meter photos become confirmed readings and trigger re-plan diffs.
- The memory sidebar shows preferences and history with forget buttons.
- Every figure opens a glass-box drawer with its formula and sources.
- The evaluation suite compares both model legs on cost and quality.
- Disclaimers, attribution, and consent flows are built in.
- The agent drives the simulated wallbox live, with approval on big actions.
- Email magic-link sign-in with sessions keeps hosted households separate.

Optional extras (Phase 4):
- Our own public MCP energy server.
- A balcony-solar teaser tab, clearly labeled as a teaser.

## UI design concepts ("Leitstand")

The interface is a dark, fully custom control room. A canvas heatmap shows
prices with an animated now-line and pulsing negative windows. The device
schedule behaves like a Gantt chart with hover details. The agent trace streams
in live, the savings odometer ticks upward, and a command palette navigates.
Prices use green, amber, and red semantics, numbers use tabular figures, and
every number carries a source chip. Motion exists only where it carries
meaning. There are five views plus a memory sidebar and a "why" overlay. This
is the winner surface, and nothing about it is off-the-shelf.

Landing wireframe:

```
┌ STROMPILOT ─────────────── DE|EN ── 🔔2 ──┐
│ "Nachtschicht, Baby schläft ab 20 Uhr,    │
│  Auto muss um 6 voll sein." [Plan machen] │
│ Heute ▓▓▓▓░░░░▓▓▓▓▓▓▓▓░░░░▓▓▓▓  Ø 31,2 ct│
│ [Wallbox 2–5h 👍👎] [WP −1,5° 18–20h] [?] │
│ Ersparnis ≈ 12,40 €/Mo ▲ │ [je Zahl: Formel]│
│ 🔌 Wallbox: lädt 11 kW · 62% ────────▶    │
└───────────────────────────────────────────┘
```

The wow moments run in this video order: a sentence becomes a day plan, the
critic catches a bad block live, negative prices start pulsing, the agent
starts the wallbox charge on camera, a "why" replay explains one block, saying
"forget my night shifts" changes behavior, and one thumbs up visibly improves
the next day's plan.

## Regulatory compliance (German domain → implementation)

- Households without a smart meter always see an "estimate on standard-profile
  basis" label, because exact billing needs interval metering.
- Wherever schedules render, we disclose that our feed is hourly while dynamic
  tariffs settle quarter-hourly.
- The all-in price is decomposed into spot price, markup, grid fees, levies,
  concession fee, electricity tax, and 19 percent VAT. Every component is
  editable, and the defaults are verified against primary sources at build
  time with source links kept in the code (an SP-02 task).
- A footer and an about page state that everything is non-binding orientation
  and not legal, tax, or investment advice. Savings always appear as ranges
  with their assumptions listed.
- Because dynamic tariffs have no price cap, the schedule view shows the worst
  hour and a monthly pattern warning.
- For privacy, a consent gate comes before any photo or AI use, photos are
  never stored by default, household data stays in local SQLite, personal data
  is stripped before any model call, forget buttons delete memories, and a
  notice names the Meta and Baseten endpoints, and deleting the account wipes
the household's data.
- Attribution stays visible: "Bundesnetzagentur | SMARD.de" for SMARD data
  under its CC BY 4.0 license, credit for aWATTar, and a citation of the 2025
  BDEW load profiles.
- Fair use is enforced by the cache, which allows roughly one live price fetch
  per day and is covered by a test. Sample mode is always labeled as sample
  mode.

## Issues

Phase 1 — Foundation:

### Issue SP-00: scaffold

Goal:

We set up the monorepo so that both toolchains run from a clean checkout.

Deliverables:

This issue delivers the repository layout with the Next.js web
app, the FastAPI API with the `strompilot` package, the evals folder, the docs
folder, all configs, environment files, the typed API contract stub, and the
README, pushed to https://github.com/qamran/strompilot.git.

Success criteria:

It succeeds when both test suites run green, both linters
pass, the API contract typechecks on both sides, and the main branch is live
on the remote.

### Issue SP-01: price feed

Goal:

We build a price feed that never breaks the demo, no matter what the
network does.

Deliverables:

This issue delivers the aWATTar client, the disk cache, the SMARD
fallback, the labeled sample fallback, the fair-use guard, and recorded
response fixtures.

Success criteria:

It succeeds when fixture tests parse responses, cache hits
work, live fetching stays at or below one call per day, and each fallback
engages in the right order.

### Issue SP-02: tariff math

Goal:

We build the household baseline and the all-in price math that every
schedule and every euro figure stands on.

Deliverables:

This issue delivers the math engine with a defaults file where
every figure links its primary source, plus the 2025 BDEW profiles and the
standard-profile labels.

Success criteria:

It succeeds when known-answer euro cases pass, the
decomposition sums correctly, and an auditor can trace each default to its
source.

### Issue SP-03: rule retrieval

Goal:

We give the agent a small, trustworthy library of tariff and regulatory
knowledge that it can cite.

Deliverables:

This issue delivers the twenty-document corpus, the chunker, the
BM25 index, and the re-ranking retriever with citations.

Success criteria:

It succeeds when golden queries retrieve the right chunks
with correct citations and negative queries retrieve nothing.

Phase 2 — Agent core:

### Issue SP-04: supervisor graph

Goal:

We build the multi-agent brain with a supervisor and four specialist
workers behind guard rails.

Deliverables:

This issue delivers the running LangGraph supervisor graph, the
analyst, scheduler, explainer, and critic workers, the typed state, and the
guard implementations.

Success criteria:

It succeeds when routing goldens pass, critic veto cases
behave correctly, and every guard trigger fires under test.

### Issue SP-05: life-to-plan

Goal:

We turn free text about a household into hard constraints, an optimal
schedule, and a cited narration.

Deliverables:

This issue delivers the extraction prompts, the Pydantic schemas,
the scheduling flow, and the narration pipeline with editable constraints.

Success criteria:

It succeeds when golden households extract exactly, citations
are present on every claim, and faithfulness spot-checks pass.

### Issue SP-06: memory

Goal:

We give the agent a memory that survives restarts and respects
forgetting.

Deliverables:

This issue delivers both SQLite stores with the preferences and
history API, including the forget endpoints.

Success criteria:

It succeeds when data survives restarts, recall returns the
right memories, and users stay isolated from each other.

### Issue SP-07: safety and human approval

Goal:

We make sure no consequential action happens without a human, no personal
data leaks to models, and no injected instruction gets obeyed.

Deliverables:

This issue delivers the approval flows, the personal-data
stripper, and the injection test set.

Success criteria:

It succeeds when approve and reject flows work end to end,
redaction cases pass, and every attack sample is blocked.

Phase 3 — Autonomy:

### Issue SP-08: Flex-Alarm

Goal:

We build a watcher that raises alerts from judgment rather than fixed
thresholds.

Deliverables:

This issue delivers the watcher loop, the alert composer, quiet
hours logic, and all delivery paths including email or push.

Success criteria:

It succeeds when synthetic price windows fire, quiet hours
suppress correctly, and no alert ever duplicates.

### Issue SP-09: meter vision

Goal:

We turn a meter photo into a confirmed reading that improves the plan.

Deliverables:

This issue delivers the photo intake endpoint, the Spark vision
extraction prompt, and the human confirm flow with the re-plan diff.

Success criteria:

It succeeds when sample fixtures extract within tolerance
and unconfirmed readings never enter the math.

### Issue SP-10: learning loop

Goal:

We close the loop so feedback visibly improves future plans.

Deliverables:

This issue delivers the feedback endpoints, the preference
updater, and the improvement tracker on golden households.

Success criteria:

It succeeds when simulated feedback shifts plans correctly
and the no-preference baseline stays stable.

### Issue SP-11: wallbox driver (MCP)

Goal:

We prove autonomy on camera by letting the agent drive a wallbox that
runs as its own program.

Deliverables:

This issue delivers the standalone MCP simulator with charge
controls and live status, the agent client wiring, and the policy gates.

Success criteria:

It succeeds when the round-trip works, gates block what they
should, and the demo shows a full cheap-window charge on camera.

Phase 4 — Product:

### Issue SP-12: Leitstand UI

Goal:

We build the winner-grade interface exactly as designed above.

Deliverables:

This issue delivers all five views, the memory sidebar, the
"why" overlay, the glass-box drawers, live trace streaming, the canvas heatmap,
the animated odometer, both languages, and all disclaimers.

Success criteria:

It succeeds when typechecks and linting pass and the smoke
suite is green on fixtures.

### Issue SP-13: full evals

Goal:

We prove quality with a real evaluation suite instead of vibes.

Deliverables:

This issue delivers the thirty-plus case dataset, the prompt
comparison runner, the cross-model judges, the faithfulness and context
metrics, the red-team set, and the CI wiring.

Success criteria:

It succeeds when the suite is green and every threshold is
documented.

### Issue SP-14: extras (optional)

Goal:

We harden delivery and optionally open our data to outside assistants.

Deliverables:

This issue delivers hardened delivery receipts and, if built,
our own public energy MCP server.

Success criteria:

It succeeds when delivery receipts arrive and the MCP
round-trip works. This issue dies silently if the core needs the time.

### Issue SP-15: authentication

Goal:

We let each household sign in with nothing but an email address, so hosted
use stays personal and memories stay private.

Deliverables:

This issue delivers the magic-link email flow, session management with secure
cookies, the sign-in and sign-out screens, the account profile page, and the
migration of a local profile into an account.

Success criteria:

It succeeds when sign-in works end to end without passwords, sessions expire
and revoke correctly, one household can never see another household's data,
and every auth path is covered by tests.

### Issue SP-16: hardening and demo

Goal:

We make the project watertight, compliant, and ready to show.

Deliverables:

This issue delivers the compliance audit reports, the Meta-only
endpoint audit, the README, the rehearsal recordings, and the demo video.

Success criteria:

It succeeds when every checklist is green and the video runs
three minutes or less.

## Build order

We build Phase 1, then 2, then 3, then 4, in issue order. Each issue's tests go
green before the next issue starts, and nothing merges on the basis of a
description alone. SP-14 is optional and dies silently if the core needs the
time.

## Validation Plan

- Every issue's tests go green before the next issue starts.
- Before we freeze, we audit every model call site and review traces to prove
  Meta-only compliance.
- We screenshot the honesty labels, ranges, and attributions as visible proof.
- We rehearse an unedited cold run until the wow moments land reliably.
- Our highest-risk check is SP-05 extraction on messy households. The
  pre-approved fallback is guided follow-up questions, which keeps the
  life-to-plan promise intact.

## Risks

- Depth competes with focus, so phase gates decide and the optional phase dies
  first.
- If Baseten lags, the demo runs on Spark alone and the open leg degrades
  gracefully.
- Surcharge defaults can drift, so parameters stay editable with sourced links
  and get re-checked at freeze.
- Frontend and backend can drift apart, so one typed contract plus shared
  fixtures keeps them together, and the frontend develops against recorded
  fixtures rather than a live backend.
- Critic and scheduler can loop, so iteration caps and a supervisor timeout
  guard them, and tests cover the behavior.

## Sources

- Key-Concepts.md in this project (sections 3, 4, 6, 8, 9, and 11 through 18,
  as cited above).
- Meta Model API quickstart: https://dev.meta.ai/docs/quickstart
- Meta Model API models: https://dev.meta.ai/docs/models
- innobu Tariff Models 2026:
  https://www.innobu.com/en/articles/tariff-models-2026-electricity-market.html
- exnaton dynamic tariffs:
  https://www.exnaton.ai/en/blog/dynamic-tariffs-flexibility-energy-transition.html
- aWATTar API: https://www.awattar.at/services/api
- BDEW standard load profiles: https://www.bdew.de/energie/standardlastprofile-strom/
- Participant guide: `meta-ai-developer-hackathon.md` in this project.
- Research ledger: `2026-10-29-six-candidates-research.md` in this project.
