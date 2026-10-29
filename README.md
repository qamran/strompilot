# Strompilot

Strompilot is an agent-first web app for German households on dynamic
electricity tariffs. A household describes its daily life in free text and
receives an optimal, explained, self-updating power plan based on live
day-ahead prices. No smart meter is required.

Every AI call goes to Meta models only: Muse Spark 1.3 on the Meta Model
API as the primary leg, and Muse Spark Open on Baseten as the second leg.

## Layout

- `web/` is the Next.js frontend (German first, English toggle).
- `api/` is the Python FastAPI backend with the `strompilot` package.
- `evals/` holds the evaluation datasets and runners.
- `docs/` holds project documentation.
- `scripts/` holds helper scripts such as key validation.
- `contract`: `api/strompilot/contract.py` and `web/lib/contract.ts` mirror
  each other and pin the same `CONTRACT_VERSION`.

## Quickstart

You need Python 3.11 or newer with `uv`, plus Node.js 20 or newer.

```sh
cp .env.example .env
# Fill in META_API_KEY and BASETEN_API_KEY in .env.

uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r api/requirements.lock
.venv/Scripts/python -m pytest api/tests
.venv/Scripts/ruff check api scripts
.venv/Scripts/mypy --config-file api/pyproject.toml api/strompilot api/tests

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

## Run the API

```sh
.venv/Scripts/python -m uvicorn strompilot.main:app --reload --app-dir api
```

Then open http://127.0.0.1:8000/health for the health check.

## Run the frontend

```sh
cd web
npm run dev
```

Then open http://localhost:3000.

## Validate the API keys

```sh
.venv/Scripts/python scripts/validate_keys.py
```

The script makes one minimal live call per provider and prints only
statuses, never key material.
