# Strompilot review notes

Written 2 November 2026, after a full pass through the code and about an hour of actually using the app.

I ran the backend (`uvicorn strompilot.main:app`) and the production frontend build (`next build && next start`), seeded the demo household, signed in as a brand-new user, typed a sentence, watched the agent work, approved the plan, and clicked through every page on a 1440px desktop and a 390px phone viewport. I also read the backend, the agent graph, the evals, and the frontend. Backend tests: 496 passed. Ruff, format check and mypy strict are all clean. `next build` and `tsc` are clean.

So I want to be fair up front: the engineering underneath is genuinely good. The optimizer is deterministic, the narration is checked against the numbers, there's a real human-in-the-loop approval step, the evals are honest, and the test suite is large. The problem is that almost none of that is visible when you use it. As a user, it feels like an internal admin console that someone forgot to finish. That's the "throwaway app" feeling, and it's fixable, mostly in the frontend and in a handful of small backend changes.

Below is everything I found, grouped and ordered by how much it matters for winning. Each item says what's wrong, where it lives, and what exactly to change. Treat the file paths and line numbers as a starting point; they were correct at commit `9e4545e`.

---

## Part 1. Things a judge will notice in the first two minutes

These are the ones I'd fix before anything else. Each one, on its own, makes the product look broken or untrustworthy.

### 1.1 The savings number is negative and it's coloured green

On the home page the savings card reads **"Savings approx. -19.33 €/mo"** in big green digits. The monthly report on `/plan` says "Savings vs flat rate: -19.33 €". So the headline message of an app about saving money on dynamic tariffs is that you lose 19 euros a month, and it's styled as good news.

- Source: `api/strompilot/report/monthly.py:163` computes `total_kwh * flat_ct_kwh / 100 - total_cost`. Rendered by `web/app/page.tsx:171` through `Odometer`.
- Fix, in this order:
  1. Check that the flat-rate comparison uses the same price basis as `total_cost` (see 1.3; I suspect one side is all-in retail and the other isn't).
  2. If the number is still negative, be honest and helpful about it: show it in amber, and change the copy to something like "This month a flat tariff would have been 19 € cheaper. Here's what to shift to change that." Then link to a plan.
  3. Better still, show the number that the app actually controls: "Your approved plans saved X € compared with running the same devices at 18:00." That's the savings Strompilot creates, and it should always be positive if the optimizer works.
  4. Never colour a value green unless it's good. Pick the colour from the sign.

### 1.2 The price chart is all one colour

The "Today" chart has a legend with four colours (Negative, Cheap, Mid, Spike), but every single bar is orange. I pulled today's series from `/prices/day-ahead`: 210 to 328 €/MWh, average around 260. The classifier in `web/lib/format.ts:27-32` calls an hour "cheap" only if it's below 70% of the average and "spike" only above 130%. On a normal German day almost nothing crosses those lines, so the chart never shows the one thing it exists to show: when power is cheap.

- Fix: classify by the day's distribution, not a fixed band around the mean. For example, cheapest 25% of hours = cheap, most expensive 15% = spike, anything below zero = negative. Or use a continuous colour scale from green to red on `(price - min) / (max - min)`.
- Also mark the cheapest window directly on the chart (a bracket or label, "Cheapest: 12:00-14:00 · 21.0 ct") and put that in the hero next to Low/Average/High (`web/app/page.tsx:102-121`). The about page already computes it (`web/app/about/page.tsx:51-56`), so move it.

### 1.3 The numbers on different pages don't agree with each other

From one session:

- Home hero: "Right now 29.8 ct/kWh", Low 21.0, Average 25.9, High 32.8.
- The plan narration: the car charges in "the cheapest hours in the window with an average of 32.58 ct per kWh".
- Alarms page: a "cheap window" at 9.16 ct/kWh against "a daily mean of 19.00 ct/kWh".
- Monthly report: "Most expensive hour ... 60.4 ct".

A judge reading this sees "cheapest hours at 32.6 ct" next to "today's high is 32.8 ct" and stops trusting anything. My best guess is that the hero shows the wholesale spot price converted to ct, the plan uses an all-in retail price (spot plus grid fees, levies, VAT), and the alarm was generated against a different day's data. Whatever the cause, it reads as a bug.

- Fix: pick one price basis for everything the user sees (all-in retail is the honest one for a household) and label it once: "All-in price incl. grid fees and taxes". If you want to show spot too, show it as a secondary line, clearly labelled.
- Put the date and the source on every price-derived number. The plan page in particular never says which day it's for (it defaults to tomorrow, `main.py:502,1377`).
- Expose `price_source` and `stale` on `PlanDetail` (`api/strompilot/main.py:1319-1329`) and render the existing `SourceChip` on the plan. See 3.1 for why this matters: right now tomorrow's plan can silently run on sample prices.

### 1.4 The phone layout is broken

At 390px wide the top nav doesn't wrap or collapse. Seven links plus Account, Ctrl+K and DE|EN push the page to roughly 950px wide, so you get horizontal scrolling and the content sits in the left third. The Alarms badge drops onto its own line and the background gradient stops halfway down.

- `web/app/globals.css:1130-1162` (the media query) never touches `.topbar` or `nav`. `web/components/Header.tsx:24-35` renders every link inline.
- Fix: below ~760px, show the logo, a menu button and the language switch; put the links in a slide-down sheet. Or use a bottom tab bar with four items (Today, Plan, Meter, Alerts) and move everything else under "More". Hide the Ctrl+K hint on touch devices. Add `aria-current="page"` and a visible active state to the current link; there isn't one on desktop either.
- Many judges will open the link on their phone. This one matters more than it looks.

### 1.5 Contradictory states on the plan page

With no plan, `/plan` shows "No plan yet. Describe your day above." and "The planner is working …" at the same time, and there's nothing "above" to describe your day in, because the input lives on the home page. After approving a plan, "The planner is working …" is still on screen.

- Fix: one status line, driven by one state value: `empty | running | waiting_for_approval | approved | failed`. For `empty`, put the sentence input right there on `/plan` instead of pointing elsewhere.

### 1.6 Memory shows duplicates, and a new user's plan doesn't create any memory

The seeded household's Memory panel lists "Geschirrspueler: Just right", "Waschmaschine: Just right" and "E-Auto: Just right" twice each. The Household page has the same six rows as "good".

As a brand-new user I typed "I work night shifts, baby sleeps from 8pm, the EV needs 30 kWh by 6am and the dishwasher runs once a day", approved the plan, and the Memory panel still said "No memories yet". The app is pitched as living memory, but the most natural moment to learn (I just told you my devices and routine) teaches it nothing.

- Fix: dedupe feedback by device and keep the latest, or aggregate it ("E-Auto: 2× just right"). After a plan is approved, offer a one-tap "Remember these devices and quiet hours?" that writes them to preferences. Then make sure the analyst actually reads them (see 2.4).

### 1.7 Dangerous buttons look like primary actions

Every button is bright green by default (`button { background: var(--accent) }` at `web/app/globals.css:399`). So "Remove", "Forget", and "Forget household …" inside the red Danger zone box are all the same cheerful green as "Make a plan" and "Approve".

- Fix: introduce button variants: primary (green, one per screen), secondary (outline), ghost (text), and danger (red outline, solid red only on the confirm step). "Remove"/"Forget" in lists should be small ghost or icon buttons, not green pills. See Part 4 for the full styling proposal.

### 1.8 Mixed language and raw machine strings in the English UI

In English mode, devices show as "Geschirrspueler" (with "ue", not even "ü") and "E-Auto". The alarm cards show raw enums and timestamps: "cheap_window", "price_spike", "delivered", "2026-11-02T07:49:31.480069Z", "Delivered via log". The agent trace shows "2026-11-02T15:26:56+00:00 perceive: intent=plan". Memory keys render as "Annual use" in a monospace font next to proportional text. Meter rows show raw `reading.status`.

- Fix: give device names a display label per language (dishwasher / Geschirrspüler, EV / E-Auto) and always store the canonical key separately. Format all times as local "15:26" or "2 Nov, 15:26". Map every enum to a translated label. Specific spots: `web/app/alarms/page.tsx:74-78`, `web/app/meter/page.tsx:138`, `web/components/Heatmap.tsx:124` (a hard-coded German aria-label), and the meter page, which titles two different cards both "Meter" (`web/app/meter/page.tsx:81` and `:118`).

---

## Part 2. The AI story: make it visible, and make the agent loop real

The judging weighs "Use of Meta AI tooling" at 25%. Right now the app uses five Meta models in genuinely clever ways, but a judge using the UI can't see any of them.

### 2.1 Show which model did what (the "glass box" is promised but not built)

The README and `docs/demo/script.md:33-34` say the glass-box drawer "shows which model wrote each block". It doesn't. The backend fills `state.attribution` in `agents/workers.py` (`_attributed()`), but `PlanDetail` (`main.py:1319-1329`) doesn't include it, `web/lib/plan.ts` never parses it, and `web/components/WhyOverlay.tsx` never renders it. The trace lines (`agents/guards.py:52-55`) are `timestamp node: detail` with no model name.

- Fix:
  1. Add `attribution: dict[str, str]` and `price_source: str` to `PlanDetail`.
  2. Include the model name in every `audit_event()`, so the trace reads "Critic · Muse Wonder · approved" rather than "critic: approved".
  3. In the plan view, put a small chip under each block: "Constraints extracted by Muse Spark 1.3 · Schedule computed deterministically · Written by Muse Spark Open · Reviewed by Muse Wonder".
  4. Redesign the trace as a vertical step list with icons, durations ("analyst · 9.1 s"), and the model name. Drop the ISO timestamps. This is your best on-screen proof of agentic behaviour, and right now it looks like a log file.

### 2.2 The critic loop doesn't actually do anything when it rejects

When Muse Wonder vetoes, `agents/supervisor.py:45` routes back to `scheduler`. The scheduler re-runs the deterministic optimizer on the same constraints, produces the same schedule, and the explainer re-drafts from the same brief. The critic's `notes` are parsed (`workers.py:225-230`) but nothing downstream reads them. In the 36-text adversarial soak, 0 runs had critic notes and 1 looped.

There's also a role overlap. The critic prompt (`workers.py:251-260`) tells Wonder "the schedule is final" and has it check the narration, which `check_faithfulness` already does deterministically.

- Fix: give the critic the one job nothing else does: check that the extracted constraints honour what the person actually said. "Baby sleeps by 8pm" should become a quiet window. "Night shift" should shift the day. "Car full by 6am" should be a deadline. On a veto, route to `analyst` and inject the critic's notes into its prompt, so the second pass is meaningfully different.
- Then make sure one demo sentence reliably triggers a single veto and a fix. "Critic: the baby's bedtime at 20:00 isn't respected, the dishwasher runs at 21:00 → analyst revised → approved" is the most convincing agentic moment you could show.

### 2.3 The plan ignores half of what the user said

My test sentence mentioned night shifts and a baby sleeping from 8pm. The narration talked only about the car and dishwasher and the "cheapest hours in the window". Nothing in the plan or its explanation acknowledges the baby or the shift. To a judge it looks as if the AI skimmed the sentence.

Also, the dishwasher was scheduled 02:00-04:00 at ~32 ct, even though midday (11:00-14:00 local) was the cheapest stretch of the day. That may be correct given the constraints the analyst extracted, but the explanation never says why.

- Fix: the explanation should name the constraint that drove each decision. "Dishwasher at 02:00, not at noon when it's cheaper, because you said you work nights and sleep during the day." "Nothing loud after 20:00, because the baby sleeps then." The citations machinery is already there; feed the constraint list into the narration brief and require at least one "because you said …" per device.
- The narration tone is stiff ("Your Geschirrspueler is scheduled to run from 02:00 to 04:00 at a cost of 0.72 Euro. It also runs then because it uses the cheapest hours in the window with an average of 32.22 ct per kWh."). Aim for two or three short, warm sentences and put the numbers in the visual. For example: "Charge the car from 2 to 6. That's 14.34 € instead of about 18 € if you plugged in after work."

### 2.4 Memory doesn't reach the planner

Only `learned_windows` gets read into planning (`agents/workers.py:135`). Saved devices and quiet hours feed the alarm watcher (`flexalarm/loop.py:19-24, 59`) but never the analyst. So the "living memory" story is thin exactly where it would matter.

- Fix: prepend one household-context line to the analyst messages in `lifeplan/extract.py:118`, something like "Known devices: dishwasher (1.2 kWh), washing machine, EV 11 kW. Quiet hours 22:00-06:00. Past feedback: EV slot 'just right' ×2." Then the demo can show a second sentence ("same as usual, but the car only needs 15 kWh") producing a correct plan without restating everything.

### 2.5 The eval judge is grading its own homework

The explainer and the judge both run on Spark Open (`agents/router.py:84-87`). `evals/judges.py:1` and `evals/thresholds.md:27` describe it as a cross-model judge. In the latest results, the judge model equals the narration model on all six cases, every case scored 5/5, and the A/B comparison came out as six ties.

- Fix: move the judge leg to Muse Wonder (with Spark as fallback) and correct the two docstrings. Add harder narration cases to `evals/cases.json`: multi-device, a device that can't be scheduled, an overnight window, English and German. Require a strict majority to declare an A/B winner. Saturated evals at 5/5 don't impress a technical judge; an eval that catches something does.

### 2.6 One input crashes the planner

In the soak, a JSON-shaped input (`offtopic-04`) made `perceive` hit "Truncated at 2000 tokens, reasoning=1998", even at minimal reasoning effort. `perceive_node` (`agents/workers.py:73-97`) has no exception handling, and `llm/client.py:124-128` doubles the budget once and then raises.

- Fix: catch `LlmError` in perceive and fail closed to `intent="other"` with an audit line "perceive failed, treated as off-topic". It's about five lines and it protects the live demo from a judge who types something weird on purpose.
- While you're there, consider folding perceive into the analyst call. The analyst returning `devices=[]` already tells you it's off-topic, and you'd save a full round trip (3-5 seconds of the ~20 s total).

### 2.7 Empty plans count as success

In the soak, 16 of 28 "published" runs had zero scheduled slots. "Save me some money on power" produced an empty plan with no explanation. The soak script counts these as wins (`scripts/soak_life_texts.py:294`).

- Fix: add a `published-empty` bucket so the metric is honest. In the product, when the analyst finds no devices, have the graph ask one clarifying question through a second `interrupt()`: "Which devices could you shift? Car, dishwasher, washing machine, heat pump?" with chips the user can tap. That turns the weakest case into a nice agentic beat.

### 2.8 Retrieval is claimed but not used

`Retriever`, BM25 and the Baseten re-ranker only appear in `evals/runner.py`. No endpoint or page uses them, yet `docs/model-usage.md` lists re-ranking as active Spark Open usage. A judge who greps will find this.

- Fix: either wire it into a small "Ask why" box on the plan ("Why is my price higher than the spot price?" answered with cited sources from the tariff corpus), or remove the claim from the model register.

### 2.9 A signature feature worth considering: read the appliance's rating plate

All six "unknown device" soak cases (sauna, kiln, pool pump) were published with zero slots: "unknown device, no power profile". You already have the pipeline to fix that. The meter path is SAM crop → Spark vision read. Point the same thing at an appliance rating plate (SAM prompt "rating plate"), read kW / voltage, save a device profile to household memory, and the device becomes plannable. It closes a measured failure, it's a 20-second camera moment in the demo, and it's a use of SAM nobody else will have.

A cheaper alternative, if time is short: voice input with Muse Voice Transcribe. It's on the hackathon model list, `docs/model-usage.md` explicitly leaves it out, and "say your day out loud" is a natural fit for a household app.

---

## Part 3. Backend reliability and security

The baseline is strong: no secrets in git, hashed tokens, uuid upload names with no path traversal, an explicit CORS allowlist, and full CI. These are the gaps.

### 3.1 Tomorrow's plan can silently run on sample prices

`api/strompilot/prices/service.py:38` skips a source if it has fetched anything from that source today. Once today's prices are cached, a request for tomorrow skips both aWATTar and SMARD and falls through to sample data, with no network call and no warning. The plan defaults to tomorrow (`main.py:502,1377`), so this is the main path. The monthly report has the same problem.

- Fix: key the fair-use log on `(source, target_date)`, not just `source`. Expose `price_source` on the plan (see 2.1) so a sample-data plan is visibly labelled. Also, `except Exception: continue` at `service.py:42` logs nothing, so add a warning log.

### 3.2 The wallbox endpoints skip both login and approval

`/wallbox/status` (`main.py:1503`) and `/wallbox/program` (`main.py:1523`) have no `Depends(current_session)`. Anyone who can reach the API can program the charger, which undercuts the whole "nothing happens without your approval" story.

- Fix: add the session dependency to both, log the household on every program call, and ideally only allow `program` from the approved-plan dispatch path.

### 3.3 Magic links are returned in the HTTP response by default

`auth/mail.py:57` defaults to `LogMailer`, and `main.py:228` then puts the link in `dev_link` in the response body. With default config, anyone can sign in as any email address.

- Fix: only return `dev_link` when an explicit `STROMPILOT_DEV_LINKS=1` is set, and log a loud warning at startup when it is. Also make token redemption atomic (`auth/store.py:85-95` is check-then-update): `UPDATE auth_tokens SET used_at=? WHERE token_hash=? AND used_at IS NULL AND expires_at>?`, then check `rowcount`. Add a basic rate limit on `/auth/request-link`.

### 3.4 Database errors show up as "unknown thread"

`main.py:1431` and `:1484` catch every `Exception` and return 404. There's no WAL mode or busy timeout on any SQLite connection, while `threads.db` is written by the background run and polled every 4 s by the page and every 0.4 s by the SSE stream. A "database is locked" error during the demo would show the judge "unknown thread".

- Fix: `PRAGMA journal_mode=WAL` and a `timeout=` on every connect. Catch only `sqlite3` and LangGraph errors, and return 503 with a retry hint.

### 3.5 The live trace goes silent after 60 seconds

The SSE loop (`main.py:1457`) runs 150 × 0.4 s and then just stops. It never sends the `[done]` sentinel that `web/components/TraceStream.tsx:19` waits for. The demo plan waits 90 seconds. If uvicorn restarts mid-run, the thread stays "running" forever.

- Fix: always send `data: [done]`, raise the time budget, and store `started_at` so a run older than N minutes becomes "failed" with a retry button.

### 3.6 The optimizer has no household power cap

`lifeplan/optimize.py:131-162` places each device independently, so the car, heat pump and dishwasher can all land in the same cheapest hour, well above a normal house connection. `lifeplan/loaders.py:55` keys price bars by `.hour`, so on DST change days you get duplicate or missing hours. (The last DST change was 25 October, so this is not hypothetical.)

- Fix: add `max_concurrent_kw` to `HouseholdConstraints` (default around 11-15 kW) and a greedy load check. Key bars by UTC start time.

### 3.7 "Forget household" doesn't forget everything

`main.py:444` deletes preferences and episodes only. Meter readings, stored photos, alerts, report art and sessions survive. The README's privacy claims are therefore overstated.

- Fix: cascade the delete across `MeterStore`, `AlertStore`, `_photos_dir`, `_art_dir` and `AuthStore`, and add a test that asserts nothing remains for that household id.

### 3.8 Reading a plan requires both LLM API keys

`get_approval_graph` and `get_plan_runner` (`main.py:494,1288`) build a full `ModelRouter` just to read a checkpoint. If a key is missing, even opening the seeded fallback plan returns a 500, and "model keys missing" wins over a 401.

- Fix: read status straight from `SqliteSaver.get_tuple()`. Only build the router when you actually need to run the graph.

### 3.9 No input limits or sane timeouts

- `PlanBody.text`, `AddEpisodeBody.text`, `FeedbackBody.note` and `SetPreferenceBody.value` have no length caps. Add `max_length` on the Pydantic fields (2,000 characters is plenty for the plan text).
- Uploads read the whole body before checking the 10 MB limit (`main.py:715,1111`). Check `Content-Length` first and stream.
- The price fetchers use 30 s timeouts × 3 requests (`prices/awattar.py:11`, `prices/smard.py:11`), so a dead network can hang `/prices/day-ahead` for 90 seconds. Use 5 s and fall back to cache straight away.
- `web/lib/api.ts:76` has no fetch timeout. Add an `AbortController` with ~15 s, and show a friendly retry state.

### 3.10 Code organisation

- `main.py` is about 1,540 lines. Split it into `APIRouter` modules per domain (auth, prices, plan, meter, alarms, memory, solar, wallbox). Add one `Settings` object and one `require_model_keys()` dependency in place of the six duplicated key checks and scattered `os.environ` lookups.
- Derive thread status from the checkpoint alone, and add a small `runs` table with `started_at` and `finished_at`. Polling should be a pure DB read, not a graph compile every 4 seconds.
- `web/lib/contract.ts` mirrors only `/health`. Around 20 response models are hand-parsed on the frontend with no drift check. Generate the TypeScript types from `/openapi.json` (openapi-typescript) in CI and fail the build on drift. That turns the "contract 0.11.0" claim into something enforced.
- Smaller items: `_read_photo` duplicates `propose_reading`. Four stores re-run `CREATE TABLE IF NOT EXISTS` on every request, so do it once at startup.

---

## Part 4. Visual design and styling

The current look ("Leitstand": dark navy, neon green, amber) is a reasonable starting point, but in practice every surface is the same dark card with the same weight. There's no hierarchy, no rhythm, and nothing that feels finished. Specific suggestions:

### 4.1 Decide what the home screen is for

Right now the home page stacks five equal cards: price, consent plus input, chart, savings, wallbox. Nothing says "start here".

Proposed structure, top to bottom:

1. **One hero sentence and the input.** "Tell me about your day. I'll plan your power around the cheapest hours." A large text area with two or three example chips beneath it ("Night shift, EV by 6am", "Home office, heat pump", "Family of four, two loads of laundry"). Tapping a chip fills the box. This is the product; it should be the first thing you see, not the second card.
2. **Today at a glance.** The price now, the cheapest window, and a colour-coded chart (fixed per 1.2), in one card.
3. **Your last plan,** if there is one, as a compact timeline with an "Open" link.
4. Everything else (wallbox, savings, memory) lower down or on its own pages.

### 4.2 Consent without friction

The checkbox-then-"I agree"-then-type-then-"Make a plan" dance (`web/components/ConsentGate.tsx`, stored in sessionStorage) shows up again in every new browser and on three different pages, and it's the first interaction a judge has.

- Fix: ask for consent once, at sign-in or on first use, as a single clear sentence with one button, and store it server-side on the household. On the input itself, a small line is enough: "Your text goes to Meta models after we strip personal details. Learn more."

### 4.3 Make the plan timeline the hero visual

The plan "Gantt" (`web/app/plan/page.tsx:31-70`, `.gantt-track` in `globals.css:544`) is a mostly empty 24-column dark grid with two short green bars. You can't see why those hours were chosen.

- Shade each hour cell of the track with the price colour, so the device bars visibly sit in the green dips.
- Label the bars inside ("EV · 30 kWh · 14.34 €").
- Add a "now" line, and labelled hour ticks at 00, 06, 12, 18.
- Show the constraint windows as hatched regions ("baby asleep", "you're at work").
- Animate the bars sliding into place when the plan arrives. Respect `prefers-reduced-motion`, which the code already handles elsewhere.
- Clicking a bar opens the "why" panel with cost, average price, the constraint that drove it, and the model attribution.

This single view, done well, is the demo.

### 4.4 Typography

Archivo plus JetBrains Mono is a fine pairing, but it's applied inconsistently. Memory keys are monospace in the middle of sentences, and the trace is raw mono log lines.

- Use a clear type scale and stick to it: for example 32/24/18/15/13 px, with 600 weight for headings and 400 for body.
- Reserve the mono font for numbers in tables and the trace's durations, not for labels.
- Keep `tabular-nums` on prices; that's good already.
- The hero price ("29.8 ct/kWh") has the number in amber and the unit in grey at the same size. Make the unit about 50% size and muted, so the number dominates.

### 4.5 Colour and buttons

- Keep the palette but give it roles. Green means "good / cheap / go". Amber means "average / attention". Red means "expensive / destructive". Cyan means "information / links". Right now green is used for everything: every button, every "Forget", every "Remove", and the negative savings number.
- Button system (fixes 1.7):
  - **Primary:** solid green, dark text, one per screen ("Make a plan", "Approve").
  - **Secondary:** 1px border in `--line`, light text ("Reject", "Check now").
  - **Ghost:** text only, for list actions ("Remove", "Forget"), possibly with a small × icon.
  - **Danger:** red outline; solid red only in the confirmation step.
- Give "Approve" and "Reject" real visual weight on the plan: a sticky bar at the bottom of the plan card while it's waiting for approval, with the total cost on it ("Approve plan · 15.06 €").

### 4.6 Spacing, surfaces, depth

- Cards all share the same background, border and padding, so the page is a column of identical boxes. Use two levels: a main surface (`--bg1`) for primary content, and an inset level (`--bg0` with an inner border) for secondary detail like the trace and citations.
- Tighten vertical spacing inside cards and widen it between sections. Put an 8 px spacing scale (8/16/24/32/48) in CSS variables and use only those values.
- **Background bug:** the body's radial gradient stops at the first viewport height, so on long pages and on mobile you can see a hard seam where the gradient ends (visible in both the desktop and mobile screenshots). Add `html { background: var(--bg0); }` and either `min-height: 100vh` on body or `background-attachment: fixed` for the gradient.

### 4.7 Empty, loading and error states

Most of these are currently plain grey sentences. Design them:

- **Empty plan:** an illustration or a faded example timeline, with "Describe your day to get your first plan" and the input right there.
- **Running:** the step list from 2.1 filling in live, each step with a spinner and then a check mark. That's 20 seconds that should feel exciting, not dead.
- **Errors:** what happened, plus a retry button. Never a raw "unknown thread".
- **Cached/sample prices:** a visible amber chip ("Using cached prices from 14:05"), not a tiny grey "Cached" tag.

### 4.8 Navigation and scope

Seven top-level nav items (Prices, Plan, Meter, Alarms, About, Household, Solar) plus Account, Ctrl+K and a language switch is too much for a hackathon demo, and it signals "feature list" rather than "product".

- Suggested nav: **Today · Plan · Meter · Alerts**, with Household, Solar and About under Account or a "More" menu.
- Hide or cut, keeping the routes and code: the Solar renovation previews (heat pump and facade have nothing to do with dynamic tariffs), the wallbox strip on the home page, "Adopt a local profile" on Account, the Ctrl+K hint, and "Generate cover art" on the plan. If you want Muse Image for the creative angle, use it in one place where it clearly helps.
- The Account page shows the internal household id (`hh_b0ecb4006f63`) and a US-format date ("12/2/2026, 4:26:52 PM") in an app aimed at German households. Hide the id, and format dates per locale.

### 4.9 Accessibility

- `WhyOverlay` has no Escape-to-close, no backdrop click, and no focus trap. Add all three.
- `Odometer.tsx:41` puts `aria-live` on a 1.2-second animation, so screen readers announce every frame. Announce only the final value.
- The "quarter-hourly" caveat appears three times on one screen (`page.tsx:166`, `plan/page.tsx:190`, `Footer.tsx:13`). Keep it in the footer only.
- Check contrast on `--faint` (#61738d) against `--bg1`; it's used for real content in places and is below 4.5:1.

---

## Part 5. The demo

The recorded video (`web/e2e/demo-video.spec.ts`) spends 13 seconds on sign-in and the account page, then opens a pre-approved seeded plan and asserts "The plan is approved". It never shows the agent working: no live trace, no critic, no approve click. Since the trace endpoint returns instantly for a published thread, the "live" trace is just a static list. Sign-in, household and solar take about 45 of the 139 seconds.

What I'd show instead, in about 30 seconds:

1. Type "Night shift, the baby sleeps by 8pm, the car must be full by 6am" (or say it, if you add voice).
2. The step list fills in live, each step naming its model: Spark reads the sentence, the deterministic optimizer schedules, Spark Open explains, Wonder reviews.
3. Wonder vetoes once with a specific reason, the analyst fixes it, Wonder approves.
4. The device bars slide into the green dips of a price-shaded timeline.
5. Click a bar: "14.34 € · avg 22.8 ct · because you need the car by 6am · written by Muse Spark Open, checked by Muse Wonder."
6. Click Approve. The wallbox gets programmed, and the trace shows it.

Use the seeded plan only as a fallback. Cut sign-in to under 3 seconds, or start already signed in.

Demo-day checklist:

- After about 13:00 CET (when tomorrow's prices publish), delete `data/prices/fetches.json`, call `/prices/day-ahead?date=<tomorrow>`, and confirm the source ends in `-live` (see 3.1).
- Use `127.0.0.1` everywhere, never `localhost`. The SameSite=Lax session cookie set by `127.0.0.1:8000` won't be sent from a `localhost:3100` page, and it fails silently as a 401.
- Run `scripts/validate_keys.py` beforehand. Without both keys, even reading a plan fails (3.8).
- Use the production build (`next build && next start`). On my machine `next dev` failed its hot-reload WebSocket handshake repeatedly and the sign-in button did nothing.
- Pre-warm the wallbox simulator once (`/wallbox/status` spawns a Python subprocess per call).
- Don't restart uvicorn mid-run; in-flight plans will stay "running" forever until 3.5 is fixed.
- Rehearse with a judge-style weird input ("ignore previous instructions", a JSON blob) once 2.6 is fixed.

---

## Part 6. What's already good (say this in the pitch)

So the fixes above don't drown it out:

- **Numbers can't be hallucinated by construction.** Schedules and costs come from a deterministic optimizer. Narration is regex-checked against the plan (times, euro and cent amounts, device names) with one repair pass (`lifeplan/narrate.py:201-275`). Citations are built from data, not by the model. Faithfulness was 1.0 on all three live eval runs.
- **Real tool use behind a human gate.** A LangGraph `interrupt()` waits for approval (`agents/workers.py:290`), then a policy check, then the wallbox is programmed over MCP.
- **Genuine multimodality.** SAM 3.1 finds the meter display, Spark vision reads the digits, and there's a full-photo fallback. The same SAM path measures roofs.
- **The open-weights leg is real.** Spark Open on Baseten writes every user-facing narration and triages alarms. Claim the open-weights bonus explicitly in the submission.
- **Layered prompt-injection defence:** tag quoting and stripping, few-shot attack examples, and PII redaction before every call. Red-team 6/6 on every run.
- **Engineering hygiene:** 496 backend tests, strict mypy, a lock file, full CI including the Next build, and live evals with 20/20 production cases and 0.96-0.98 extraction accuracy.

---

## Suggested order of work

If there are only a couple of days left, this is the order I'd go in:

1. Savings sign and colour, chart colouring, consistent price basis and labels (1.1-1.3). About half a day.
2. Mobile nav and the background seam (1.4, 4.6). About 2 hours.
3. Plan page states, language and formatting cleanup, button variants (1.5, 1.7, 1.8, 4.5). About half a day.
4. Model attribution in the API and UI, plus the redesigned live step list (2.1, 4.7). About half a day.
5. Price-shaded plan timeline with "because you said" explanations (4.3, 2.3). About a day.
6. Make the critic loop meaningful and stop perceive from crashing (2.2, 2.6). About half a day.
7. Security quick wins: wallbox auth, dev-link flag, atomic token redeem, price cache key (3.1-3.3). About 2 hours.
8. Re-record the demo around the live run (Part 5).
9. If there's time left: the rating-plate reader or voice input (2.9), and the `main.py` split (3.10).
