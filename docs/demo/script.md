# Demo video script — Strompilot (2:19)

Spoken English, narrated by a synthetic voice over the scripted tour
in `web/e2e/demo-video.spec.ts`. The words below match the recording
in `strompilot-demo.mp4` exactly. Times are approximate beat windows.

## Beat 1 — Sign in (0:00–0:13)

Video: `/signin`, fill the demo address, open the dev link, land on
`/account` showing the profile.

> Meet Strompilot, the agent-first power planner for German homes on
> dynamic tariffs. One email signs you in — no password — and every
> household keeps its own private data. On the account page you see
> the profile, the session, and one click adopts a local demo into
> your private household.

## Beat 2 — Live prices (0:13–0:42)

Video: `/` hero price, heatmap scroll, savings panel, plan box.

> Day-ahead prices stream in live. The heatmap shows the next cheap
> windows at a glance, and the planner already knows what tonight
> costs against a flat tariff. Prices come from aWATTar with SMARD
> as fallback, always labeled, so you know exactly which source
> you see.

## Beat 3 — The plan (0:42–1:23)

Video: `/plan?thread=...` gantt, why-block dialog, trace scroll.

> Here is last night's plan: washer, dishwasher, and the car, each
> placed in its cheapest hours. Every slot explains itself, every
> number traces back to a source, and the glass box shows which
> model wrote each block. Plans pause for your approval, learn from
> your thumbs up or down, and the agent trace shows every step the
> supervisor took.

## Beat 4 — Meter truth (1:23–1:35)

Video: `/meter` readings list with serials and a kept photo.

> The meter keeps the plan honest. Vision reads the dial and the
> serial, you confirm, and the numbers feed back into planning.
> Photos stay on your machine unless you explicitly keep them, and
> every reading shows its meter number.

## Beat 5 — Alarms (1:35–1:47)

Video: `/alarms` watch report with delivery receipts.

> A watcher judges every price window and delivers flex alarms with
> receipts — while quiet hours keep the nights silent. Negative
> prices and spikes get their own alarm kinds, and every delivery
> leaves a receipt with its channel and time.

## Beat 6 — Household (1:47–1:57)

Video: `/household` devices and quiet hours.

> Devices, quiet hours, and usage live here, learned from your own
> words or managed by hand. Quiet hours hold back the night alarms,
> and the annual figure keeps the savings math honest.

## Beat 7 — Solar teaser (1:57–2:14)

Video: `/solar` upload, roof boxes, panel estimate.

> And a glimpse ahead: SAM outlines your roof and estimates the
> panel fit, with every assumption on the table. Renovation previews
> then show solar panels, a heat pump, or new cladding on your own
> photo, every one labeled as an AI visualization.

## Beat 8 — Close (2:14–2:19)

Video: `/about` live stats.

> Strompilot: Meta models only, explained end to end, ready for
> your home. The About page closes the loop with live stats and
> the full pipeline, from free text to finished plan.

## Re-recording

```sh
cd web
$env:DEMO_VIDEO = "1"
npx playwright test -c playwright.video.config.ts
```

The tour records to `test-results/demo-video-demo-tour-chromium/`,
skips in the normal suite, and reuses the seeded demo household.
Mux narration with ffmpeg and keep the result under three minutes.
