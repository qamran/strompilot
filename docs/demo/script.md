# Demo video script — Strompilot (2:14)

Spoken English, narrated by a synthetic voice over the scripted tour
in `web/e2e/demo-video.spec.ts`. The words below match the recording
in `strompilot-demo.mp4` exactly. Times are approximate beat windows.

## Beat 1 — Sign in (0:00–0:08)

Video: `/signin`, fill the demo address, tick consent, open the dev
link, land on `/account`, leave immediately.

> Meet Strompilot, the agent-first power planner for German homes.
> One email signs you in, one checkbox agrees to planning.

## Beat 2 — Today at a glance (0:08–0:23)

Video: `/` tagline and consent line, price hero, heatmap scroll.

> Day-ahead prices stream in live, all-in with grid fees and taxes.
> The hero names the current hour, the heatmap shows the next cheap
> windows, and every figure carries its source.

## Beat 3 — The live plan (0:23–1:12)

Video: `/` plan box, submit the sentence, `/plan?thread=...` live
trace filling in, pause note, gantt block dialog, Approve click,
"Program wallbox" in the trace.

> Night shift, the baby sleeps by 8pm, the car must be full by 6am.
> Watch the trace: Spark reads the sentence, the deterministic
> optimizer schedules, Spark Open explains, Wonder reviews — every
> step names its model. On a good take Wonder vetoes once with a
> specific reason and the analyst fixes it before anything runs.
> The device bars slide into the green dips of the price-shaded
> timeline. Click a bar: cost, average rate, the reason you gave,
> written by Spark Open and checked by Wonder. One click approves,
> and the trace shows the wallbox being programmed.

Fallback: if the run stalls past seven minutes the tour opens the
seeded approved plan instead and continues with the same block
dialog. Prefer a live take; re-record until the critic visibly
reviews.

## Beat 4 — Meter truth (1:12–1:26)

Video: `/meter` readings list with serials and a kept photo.

> The meter keeps the plan honest. Vision reads the dial and the
> serial, you confirm, and the numbers feed back into planning.
> Photos stay on your machine unless you explicitly keep them.

## Beat 5 — Alarms (1:26–1:34)

Video: `/alarms` watch report with delivery receipts.

> A watcher judges every price window and delivers flex alarms with
> receipts — while quiet hours keep the nights silent.

## Beat 6 — Household (1:34–1:42)

Video: `/household` devices, quiet hours, consent section.

> Devices, quiet hours, and usage live here, learned from your own
> words or managed by hand. Consent is agreed and revoked in one
> place.

## Beat 7 — Solar teaser (1:42–2:01)

Video: `/solar` upload, roof boxes, panel estimate.

> And a glimpse ahead: SAM outlines your roof and estimates the
> panel fit, with every assumption on the table. Renovation previews
> then show solar panels, a heat pump, or new cladding on your own
> photo, every one labeled as an AI visualization.

## Beat 8 — Close (2:01–2:14)

Video: `/about` title and live stats.

> Strompilot: Meta models only, explained end to end, ready for
> your home.

## Re-recording

```sh
cd web
$env:DEMO_VIDEO = "1"
npx playwright test -c playwright.video.config.ts
```

The tour records to `test-results/demo-video-demo-tour-chromium/`,
skips in the normal suite, and reuses the seeded demo household.
It needs both model keys for the live plan leg; the seeded thread
covers a keyless room. Mux narration with ffmpeg and keep the
result under three minutes.
