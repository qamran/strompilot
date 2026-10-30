"""Record web fixtures from the API over fakes.

Every JSON file under web/fixtures is a real response body captured through
the FastAPI test client, so the smoke suite tests the parsers and views
against the true contract shapes.
"""

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))


from fastapi.testclient import TestClient
from strompilot.flexalarm.store import AlertStore
from strompilot.llm.client import SPARK_OPEN_MODEL, WONDER_MODEL
from strompilot.main import (
    PlanRunner,
    app,
    get_plan_runner,
    get_wallbox_client,
)
from strompilot.memory.store import MemoryStore
from strompilot.metervision.store import MeterStore
from tests.fakes import (
    FakeRouter,
    FakeWallbox,
    idle_wallbox_status,
    reply,
    stub_loader,
)
from tests.test_graph import APPROVE

HOUSEHOLD = "demo-haushalt"

ANALYST_JSON = """{"facts": ["billig nachts"],
"devices": [
{"device": "Waschmaschine", "power_kw": 2.0, "duration_h": 2.0,
"earliest": "00:00", "latest": "23:00", "shiftable": true}
],
"notes": ""}"""

NARRATION = (
    "Die Waschmaschine läuft von 02:00 bis 04:00 Uhr und kostet 0,60 €. "
    "Die Gesamtkosten betragen 0,60 €."
)


def main() -> None:
    """Capture one fixture per view into web/fixtures."""
    scratch = Path(tempfile.mkdtemp(prefix="strompilot-fixtures-"))
    memory_db = scratch / "memory.db"
    threads_db = scratch / "threads.db"
    os.environ["MEMORY_DB"] = str(memory_db)
    os.environ["THREADS_DB"] = str(threads_db)
    os.environ["PRICE_CACHE_DIR"] = str(scratch / "prices")
    os.environ["REPORT_ART_DIR"] = str(scratch / "art")

    memory = MemoryStore(memory_db)
    memory.set_preference(HOUSEHOLD, "night_shift", True)
    memory.add_episode(HOUSEHOLD, "note", "Baby schläft ab 20 Uhr.")
    AlertStore(memory_db).record(
        household_id=HOUSEHOLD,
        dedup_key="cheap-2026-06-01",
        kind="cheap",
        title="Billige Nachtstunden",
        body="02:00 bis 04:00 Uhr kosten unter 15 ct/kWh.",
        status="delivered",
        channel=None,
        reason="scanner",
    )
    MeterStore(memory_db).propose(
        household_id=HOUSEHOLD,
        value_kwh=12345.6,
        read_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
        confidence="high",
        sam_box="10,20,300,120",
        photo_path="",
    )

    router = FakeRouter(
        {
            "supervisor": [reply("plan")] * 4,
            "analyst": [reply(ANALYST_JSON)] * 4,
            "explainer": [reply(NARRATION, SPARK_OPEN_MODEL)] * 4,
            "critic": [reply(APPROVE, WONDER_MODEL)] * 4,
        }
    )
    runner = PlanRunner(
        router=router,
        loader_for=lambda day: stub_loader,
        threads_db=threads_db,
        memory=memory,
        wallbox=FakeWallbox([idle_wallbox_status()] * 4),
    )
    app.dependency_overrides[get_plan_runner] = lambda: runner
    app.dependency_overrides[get_wallbox_client] = lambda: FakeWallbox(
        [idle_wallbox_status()]
    )
    client = TestClient(app)

    fixtures: dict[str, object] = {}
    res = client.get("/prices/day-ahead", params={"date": "2026-06-01"})
    res.raise_for_status()
    fixtures["prices"] = res.json()

    created = client.post(
        "/plan",
        json={
            "household_id": HOUSEHOLD,
            "text": "Waschmaschine nachts laufen lassen",
            "plan_day": "2026-06-01",
        },
    )
    created.raise_for_status()
    thread_id = created.json()["thread_id"]
    detail = client.get(f"/plan/{thread_id}")
    detail.raise_for_status()
    fixtures["plan"] = detail.json()

    res = client.get("/flexalarm/alerts", params={"household_id": HOUSEHOLD})
    res.raise_for_status()
    fixtures["alerts"] = res.json()

    res = client.get("/meter/readings", params={"household_id": HOUSEHOLD})
    res.raise_for_status()
    fixtures["readings"] = res.json()

    res = client.get(
        "/report/monthly",
        params={"household_id": HOUSEHOLD, "month": "2026-05"},
    )
    res.raise_for_status()
    fixtures["report"] = res.json()

    res = client.get("/wallbox/status")
    res.raise_for_status()
    fixtures["wallbox"] = res.json()

    res = client.get("/memory/preferences", params={"household_id": HOUSEHOLD})
    res.raise_for_status()
    fixtures["preferences"] = res.json()

    res = client.get("/memory/history", params={"household_id": HOUSEHOLD})
    res.raise_for_status()
    fixtures["history"] = res.json()

    out_dir = ROOT / "web" / "fixtures"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in fixtures.items():
        (out_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    app.dependency_overrides.clear()
    print(f"recorded {len(fixtures)} fixtures in {out_dir}")


if __name__ == "__main__":
    main()
