"""Live injection probe: every attack sample must stay blocked.

Reads api/tests/fixtures/attack_samples.json, runs each text through
Spark extraction, and fails when any sample leaks, breaks the schema,
or yields unexpected devices. Needs META_API_KEY plus BASETEN_API_KEY.
Run manually; the suite stays offline.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "api")

from dotenv import load_dotenv
from strompilot.agents.router import ModelRouter
from strompilot.lifeplan.extract import analyze
from strompilot.llm.types import LlmError

load_dotenv(".env")
try:
    meta_key = os.environ["META_API_KEY"]
    baseten_key = os.environ["BASETEN_API_KEY"]
except KeyError as exc:
    raise SystemExit(f"missing key: {exc}") from exc

router = ModelRouter.from_keys(meta_key, baseten_key)
samples = json.loads(
    Path("api/tests/fixtures/attack_samples.json").read_text(encoding="utf-8")
)

failures = 0
for sample in samples:
    try:
        analysis = analyze(sample["text"], router)
    except LlmError as exc:
        failures += 1
        print(f"FAIL {sample['name']}: extraction broke: {exc}")
        continue
    got = [device.device for device in analysis.constraints.devices]
    dump = json.dumps(
        {
            "devices": [d.model_dump() for d in analysis.constraints.devices],
            "facts": analysis.facts,
            "notes": analysis.constraints.notes,
        }
    )
    leaked = [s for s in sample["must_not_contain"] if s in dump]
    if got == sample["expected_devices"] and not leaked:
        print(f"BLOCKED {sample['name']} (devices {got})")
    else:
        failures += 1
        print(f"FAIL {sample['name']}: devices {got}, leaked {leaked}")

total_usd = sum(entry.cost_usd or 0.0 for entry in router.spend_log)
print(f"spend: {len(router.spend_log)} calls, ${total_usd:.4f} priced")
if failures:
    raise SystemExit(f"{failures} attack samples got through")
