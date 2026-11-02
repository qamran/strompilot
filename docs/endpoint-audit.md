# Meta-only endpoint audit (SP-16)

Checked 2026-11-02 against the working tree. Method: every outbound
HTTP call site was listed by searching for `httpx.get`, `httpx.post`,
and `httpx.Client` under `api/strompilot` and `api/wallbox`, and every
hardcoded `https://` host under `api`, `scripts`, and `evals` was
classified as model, data, delivery, or citation.

## Verdict

Every model call in Strompilot goes to exactly two hosts: the Meta
Model API and Baseten. No OpenAI, Anthropic, Google, or other model
endpoint appears anywhere in the code, scripts, evals, or fixtures.

## Model endpoints

| Host | Constant | Callers | Use |
|---|---|---|---|
| `https://api.meta.ai/v1` | `META_BASE_URL` in `api/strompilot/llm/client.py` | `llm/client.py`, `metervision/sam.py`, `report/images.py` | Spark, Wonder, SAM 3.1, Muse Image |
| `https://inference.baseten.co/v1` | `BASETEN_BASE_URL` in `api/strompilot/llm/client.py` | `llm/client.py` | Spark Open volume legs |

Pinning evidence: `api/tests/test_image_client.py` asserts the exact
images URL and `muse-image-1.0`; `api/tests/test_sam_client.py`
asserts the `/responses` URL and `sam-3.1`; the router tests assert
`muse-spark-1.3` and `meta-models/muse-spark-open-1026`.
`scripts/validate_keys.py` probes the same two hosts and no others.

## Data endpoints (not models)

| Host | Caller | Use |
|---|---|---|
| `https://api.awattar.de/v1/marketdata` | `prices/awattar.py` | Day-ahead prices |
| `https://www.smard.de/app/chart_data/4169/DE-LU` | `prices/smard.py` | Day-ahead prices, fallback source |

## Delivery endpoints (not models)

| Target | Caller | Notes |
|---|---|---|
| Household webhook URL | `flexalarm/senders.py` | Operator-configured, `https://` enforced, alert JSON only |
| Log sender | `flexalarm/senders.py` | No network use at all |
| SMTP host | `auth/mail.py` | Only when `STROMPILOT_MAILER=smtp`; default mailer logs |

## Citation strings (never fetched)

`retrieval/data/corpus.json`, `tariff/data/h25_2025.json`, and
`tariff/defaults.py` carry `source_url` strings (laws, levy notices,
price factsheets) that are shown to users as citations. No code path
fetches them; the only readers are the citation builders and their
tests.
