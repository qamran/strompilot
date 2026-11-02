# Compliance audit (SP-16)

Checked 2026-11-02 against the working tree. Every item names the
code and the test that prove it.

## Access control

- [x] Every household-data endpoint requires a session cookie and
  rejects anonymous calls with 401. Guard: `current_session` plus
  `_guard` in `api/strompilot/main.py`. Proof:
  `api/tests/test_auth_api.py::test_household_endpoints_enforce_the_session`.
- [x] A session can only touch its own household; foreign ids get
  403. Proof: `api/tests/test_memory_api.py::test_households_stay_isolated`
  and a live two-household check (own 200, foreign 403, anonymous 401).
- [x] Plan threads are owner-checked against checkpoint state, and
  crash remnants against the crash table's household column. Proof:
  `api/tests/test_plan_api.py`, `api/tests/test_approval_api.py`.
- [x] Sessions expire after 30 days, revoke on sign-out, and are
  stored hashed (sha256) so a database leak stays useless. Proof:
  `api/tests/test_auth_store.py`.
- [x] Magic links are single-use, expire after 15 minutes, and are
  stored hashed. The token never appears in SMTP mode responses.
  Proof: `api/tests/test_auth_api.py`, `api/tests/test_auth_mail.py`.

## Privacy and consent

- [x] Meter photos are processed in memory and stored only when the
  household ticks keep-photo behind the consent bar. Proof:
  `propose_reading` in `api/strompilot/main.py`,
  `api/tests/test_meter_api.py`.
- [x] Stored photos are served household-scoped (`_guard` on the
  photo route), never by bare id. Proof: `test_meter_api.py`.
- [x] Consent is a slim non-blocking bar per feature
  (plan, photo, watch, solar), remembered per tab in sessionStorage,
  never in a cookie, never sent to the server. Proof:
  `web/components/ConsentGate.tsx`, the consent e2e journey.
- [x] Forgetting a household deletes its preferences and memories;
  sign-out revokes the session. Proof: `test_memory_api.py`,
  `test_auth_api.py::test_sign_out_revokes_the_session`.

## Secrets

- [x] API keys live in `.env` only, read via `os.environ`, and
  `.env` never entered git history (`git log -- .env` is empty).
- [x] No key is ever logged: no logger or print call in
  `api/strompilot` touches a key value.
- [x] Cookies are HttpOnly with SameSite=Lax, Secure on hosted
  builds via `STROMPILOT_COOKIE_SECURE`. CORS allows credentials
  only for the local frontend origins. Proof: `main.py` middleware
  plus `_set_session_cookie`.

## AI honesty

- [x] Every renovation preview carries an AI-visualization label in
  the user's language. Proof: `api/tests/test_solar_api.py`,
  `web/lib/solar.test.ts`.
- [x] The roof estimate ships its assumptions (straight-on photo,
  70% usable, panel size, Berlin yield). Proof:
  `api/tests/test_solar.py`.
- [x] Prices carry source chips (aWATTar vs SMARD), plans carry
  citations, and the demo crib sheet lists the tariff caveats
  openly. Proof: `docs/demo-plan.md`, `web/components/SourceChip.tsx`.

## Failure behavior

- [x] Model and price failures fail loudly (502/500 with a reason),
  never as silent zeros. Proof: the missing-keys tests across the
  API suites, `test_vision_failure_returns_502`.
- [x] Plan crashes persist as blocked threads with server
  tracebacks, visible only to the owning household. Proof:
  `test_crashed_run_reads_back_as_blocked_with_error` plus thread
  ownership in `read_plan`.
