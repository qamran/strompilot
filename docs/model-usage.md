# Model usage register — Strompilot

Every AI call in Strompilot goes to Meta models only. This register lists
each model, where the product uses it, and what happens when it fails. It
exists so judges and auditors can verify our Meta tooling use in one place.

## Active usage

| Model | Endpoint | Used in | Purpose | Volume | On failure |
|---|---|---|---|---|---|
| Muse Spark 1.3 | Meta Model API | SP-04 supervisor, analyst; SP-05 extraction; SP-09 digit reading | Hard reasoning, reliable extraction, and scene understanding | Every plan | Retry, then fail loudly |
| Muse Spark Open | Baseten inference | SP-05 narration; SP-03 re-ranking; SP-08 triage; SP-13 judges | High-volume jobs | Many calls per plan | Per-call fallback to Muse Spark |
| Muse Wonder | Meta Model API | SP-04 critic | Final quality gate on every plan | One review per plan | Muse Spark acts as critic |
| SAM 3.1 | Meta Model API | SP-09 meter intake | Segment the meter display via text prompts before digit reading | One call per photo | Read the full photo without a mask |
| SAM 3.1 | Meta Model API | SP-14 solar teaser (optional) | Outline usable roof area for the panel-fit estimate | One call per roof photo | Skip the estimate, keep the teaser text |
| Muse Image | Meta Model API | SP-12 monthly report | Personalized report illustration | One image per household per month | Ship the report without illustration |
| Muse Image | Meta Model API | SP-14 renovation teaser (optional) | Renovation previews on the household's own photo, labeled as AI visuals | One preview per request | Show the original photo with a notice |

## SAM 3.1 notes

- SAM 3.1 is the latest SAM version served on the Meta Model API under the
  model id sam-3.1, called over POST /v1/responses with the same Bearer key
  as everything else. Meta's docs position 3.1 as the API-served release on
  purpose-built DETR inference, but publish no itemized 3-versus-3.1 delta,
  so this register claims none.
- Prompts are short noun phrases naming one concept per request, such as
  electricity meter or roof surface. Commands and questions are unreliable.
- The docs recommend Spark for scene understanding first, then passing the
  named concept to SAM for masks. SP-09 follows exactly that pattern.

## Possible later, not in the plan

- Window counting for heat-loss estimates stays out because the plan has no
  building-physics engine, and heat loss is a different product from tariff
  planning.
- Video walkthrough highlighting stays out because SP-09 covers photo intake,
  and video upload and tracking need product surface that does not exist yet.
- Thermal hotspot detection stays out because thermal cameras are rare
  hardware, and the feature would serve almost no household.

## Evaluated but not used

- Muse Glimmer stays out because Spark Open already covers the open-weights
  leg, and a third leg adds complexity without a distinct job.
- Muse Voice Transcribe stays out because the product has no voice input in
  v1. Reading meters aloud by phone call is a possible later use.
- Embeddings and vector search stay out because Meta offers no embedding
  model, so rule lookup uses BM25 keyword search instead.

## Reasoning effort

- Muse Spark always reasons, and with no effort bound it can spend the
  whole token budget thinking and return no content (seen live). Every
  call pins `reasoning_effort`: `minimal` for one-word answers,
  `low` for everything else. Verified live on Spark, Wonder, and
  Spark Open through Baseten.

## Pricing notes

- Muse Spark costs $1.25 input and $4.25 output per 1M tokens, so
  the router prices Spark legs in the spend log.
- Muse Wonder costs $4.00 input and $20.00 output per 1M tokens, so
  critic-only use keeps the volume tiny.
- SAM 3.1 costs $2.50 per 1k images, at one call per meter photo.
- Muse Image costs $0.01 per image, at one image per household per month.
- Re-check https://dev.meta.ai/docs/pricing-rate-limits before the freeze.

## Audit support

- The SP-16 endpoint audit checks every model call site against this register.
- Every plan block records which model wrote it, shown in the glass-box drawer.
