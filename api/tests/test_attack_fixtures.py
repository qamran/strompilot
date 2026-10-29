"""Shape guard for the injection attack fixture.

The live attack script (not the suite) proves the model blocks these
samples, because prompt behavior needs the real model.
"""

import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "attack_samples.json"


def test_attack_fixture_parses() -> None:
    samples = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(samples) >= 4
    for sample in samples:
        assert sample["name"].strip() != ""
        assert sample["text"].strip() != ""
        assert isinstance(sample["expected_devices"], list)
        assert isinstance(sample["must_not_contain"], list)
