"""Live meter check: every fixture must read within tolerance.

Runs the full vision pipeline (SAM 3.1 plus Spark) over the synthetic
meter photos in api/tests/fixtures/meter/ and fails when any reading
lands more than 0.2 kWh off. Needs META_API_KEY plus BASETEN_API_KEY.
Run manually; the suite stays offline.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "api")

from dotenv import load_dotenv
from strompilot.agents.router import ModelRouter
from strompilot.metervision.pipeline import process_photo
from strompilot.metervision.sam import SamClient

TOLERANCE_KWH = 0.2

load_dotenv(".env")
try:
    meta_key = os.environ["META_API_KEY"]
    baseten_key = os.environ["BASETEN_API_KEY"]
except KeyError as exc:
    raise SystemExit(f"missing key: {exc}") from exc

router = ModelRouter.from_keys(meta_key, baseten_key)
sam = SamClient(meta_key)
root = Path("api/tests/fixtures/meter")
fixtures = json.loads((root / "meter_fixtures.json").read_text(encoding="utf-8"))

failures = 0
for fixture in fixtures:
    photo = (root / fixture["file"]).read_bytes()
    try:
        proposal = process_photo(photo, "image/png", sam, router)
    except Exception as exc:  # noqa: BLE001 - report, don't crash the run
        failures += 1
        print(f"FAIL {fixture['name']}: pipeline broke: {exc}")
        continue
    error = abs(proposal.value_kwh - fixture["expected_kwh"])
    serial_ok = proposal.serial == fixture.get("expected_serial")
    serial_note = f"serial {proposal.serial}"
    box_note = "no box"
    box_ok = True
    if proposal.sam_box is not None:
        box = proposal.sam_box
        lcd = fixture["lcd"]
        center = ((box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2)
        inside = lcd[0] <= center[0] <= lcd[2] and lcd[1] <= center[1] <= lcd[3]
        box_ok = inside
        box_note = f"box {box.x1},{box.y1},{box.x2},{box.y2} c={box.confidence}"
    if error <= TOLERANCE_KWH and box_ok and serial_ok:
        print(
            f"PASS {fixture['name']}: {proposal.value_kwh} kWh "
            f"(expected {fixture['expected_kwh']}, {box_note}, {serial_note})"
        )
    else:
        failures += 1
        print(
            f"FAIL {fixture['name']}: {proposal.value_kwh} kWh "
            f"(expected {fixture['expected_kwh']}, {box_note}, {serial_note})"
        )

total_usd = sum(entry.cost_usd or 0.0 for entry in router.spend_log)
print(f"spend: {len(router.spend_log)} calls, ${total_usd:.4f} priced")
if failures:
    raise SystemExit(f"{failures} fixtures missed tolerance")
