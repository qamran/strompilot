"""Shape guard for the golden household fixture.

The live golden script (not the suite) proves extraction matches these
households exactly, because the prompt behavior needs the real model.
"""

import json
from pathlib import Path

from strompilot.lifeplan.schemas import HouseholdConstraints

FIXTURE = Path(__file__).parent / "fixtures" / "golden_households.json"


def test_golden_fixture_parses() -> None:
    goldens = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(goldens) >= 3
    for golden in goldens:
        assert golden["name"].strip() != ""
        assert golden["text"].strip() != ""
        expected = HouseholdConstraints.model_validate(golden["expected"])
        assert len(expected.devices) >= 1
