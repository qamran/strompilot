# Strompilot

Strompilot is an agent-first web app for German households on dynamic
electricity tariffs. A household describes its daily life in free text and
receives an optimal, explained, self-updating power plan based on live
day-ahead prices. No smart meter is required.

Every AI call goes to Meta models only: Muse Spark 1.3 on the Meta Model
API as the reasoning leg, Muse Spark Open on Baseten as the volume leg,
Muse Wonder as the plan critic, SAM 3.1 for vision segmentation, and
Muse Image for illustrations and renovation previews. The full register
lives in `docs/model-usage.md`, and `docs/endpoint-audit.md` proves no
other model endpoint is called.

## What it does

- **Plans**: free text becomes an approved, explained charging and
  appliance schedule on live prices, with citations and a glass-box
  drawer that shows which model wrote each block.
- **Meters**: meter photos are read by vision (SAM crop plus Spark
  digits), confirmed by hand, and folded back into planning.
- **Alarms**: a watcher judges cheap and spike windows and delivers
  flex alarms with receipts, holding quiet hours.
- **Memory**: devices, quiet hours, usage, and feedback persist per
  household and steer future plans.
- **Accounts**: passwordless magic-link sign-in, one private household
  per email, one-click adoption of a local profile.
- **Solar teaser**: SAM outlines the roof for a panel-fit estimate,
  and Muse Image renders renovation previews on the household's own
  photo, always labeled as AI visualizations.

## Layout

- `web/` is the Next.js frontend (English default, German toggle).
- `api/` is the Python FastAPI backend with the `strompilot` package.
- `evals/` holds the evaluation datasets and runners.
- `docs/` holds project documentation, the demo runbook, and audits.
- `scripts/` holds helper scripts such as key validation and seeding.
- `contract`: `api/strompilot/contract.py` and `web/lib/contract.ts`
  mirror each other and pin the same `CONTRACT_VERSION` (0.11.0).

## Quickstart

You need Python 3.11 or newer with `uv`, plus Node.js 20 or newer.

```sh
cp .env.example .env
# Fill in META_API_KEY and BASETEN_API_KEY in .env.

uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r api/requirements.lock
.venv/Scripts/python -m pytest api/tests
.venv/Scripts/ruff check api scripts evals
.venv/Scripts/ruff format --check api scripts evals
.venv/Scripts/mypy --config-file api/pyproject.toml api/strompilot api/wallbox api/tests

cd web
npm install
npm test
npm run typecheck
npm run lint
```

On macOS and Linux the Python commands use `.venv/bin/python` instead of
`.venv/Scripts/python`.

The lock file `api/requirements.lock` pins every backend dependency, so all
checkouts install identical versions. Regenerate it from the project root
after changing dependencies:

```sh
uv pip compile api/requirements.in -o api/requirements.lock
```

Price data caches under `data/prices/` (gitignored). Override the location
with the `PRICE_CACHE_DIR` environment variable. Refresh the recorded test
fixtures with `.venv/Scripts/python scripts/record_price_fixtures.py`, which
makes one live call per source.

## Run the app

Start the backend from the project root:

```sh
cd api
..\.venv\Scripts\python -m uvicorn strompilot.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000/health for the health check and
http://127.0.0.1:8000/docs for the API reference.

Build and start the frontend from the project root:

```sh
cd web
npm run build
npm run start -- --port 3100
```

Then open http://127.0.0.1:3100/ and sign in on `/signin`. Local
development uses the log mailer, so the sign-in page shows the magic
link directly.

Seed the showcase household (signs in as `demo@example.de` by itself):

```sh
.venv/Scripts/python scripts/seed_demo.py
```

## Validate the API keys

```sh
.venv/Scripts/python scripts/validate_keys.py
```

The script makes one minimal live call per provider and prints only
statuses, never key material.

## Demo

- The six-minute judge script with fallbacks: `docs/demo-plan.md`.
- The recorded tour (three minutes or less): `docs/demo/strompilot-demo.mp4`.
- The narration script behind the recording: `docs/demo/script.md`.

## Docs

- `docs/Project-Plan.md`: the SP-00 to SP-16 work plan behind the issues.
- `docs/model-usage.md`: the model register for judges and auditors.
- `docs/endpoint-audit.md`: proof that models come from Meta only.
- `docs/compliance-audit.md`: access, privacy, secrets, and honesty checks.
- `docs/demo-plan.md`: the live demo runbook.
- `docs/design-references.md`: the UI references behind the Leitstand look.
