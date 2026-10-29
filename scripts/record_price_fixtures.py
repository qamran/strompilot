"""Record one live price fixture per source for the SP-01 test suite.

Makes one data call to aWATTar DE and one index plus one data call to
SMARD, then saves the raw responses under api/tests/fixtures/. Run again
only when a fixture must be refreshed; the suite never touches the
network afterwards.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from strompilot.prices.models import BERLIN
from strompilot.prices.smard import select_week_file, week_timestamps

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "api" / "tests" / "fixtures"
TIMEOUT_SECONDS = 30.0


def fetch_awattar() -> dict:
    """Fetch the last 24 hours of German day-ahead prices from aWATTar."""
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 24 * 3600 * 1000
    url = f"https://api.awattar.de/v1/marketdata?start={start_ms}&end={now_ms}"
    response = httpx.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    print(f"awattar: HTTP {response.status_code}, {len(data)} intervals")
    return payload


def fetch_smard() -> tuple[dict, dict]:
    """Fetch the current week file of German day-ahead prices from SMARD."""
    base = "https://www.smard.de/app/chart_data/4169/DE-LU"
    index_response = httpx.get(f"{base}/index_hour.json", timeout=TIMEOUT_SECONDS)
    index_response.raise_for_status()
    index_payload = index_response.json()
    timestamps = week_timestamps(index_payload)
    today = datetime.now(BERLIN).date()
    week_ts = select_week_file(timestamps, today)
    print(f"smard: index lists {len(timestamps)} weeks, selected {week_ts}")
    url = f"{base}/4169_DE-LU_hour_{week_ts}.json"
    response = httpx.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    series = payload.get("series", payload.get("data", []))
    print(f"smard: HTTP {response.status_code}, {len(series)} points")
    return payload, index_payload


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    try:
        awattar = fetch_awattar()
        smard, index = fetch_smard()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"recording failed: {exc}")
        return 1
    (FIXTURES / "awattar_de.json").write_text(
        json.dumps(awattar, indent=2), encoding="utf-8"
    )
    (FIXTURES / "smard_4169.json").write_text(
        json.dumps(smard, indent=2), encoding="utf-8"
    )
    (FIXTURES / "smard_index.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    print(f"fixtures saved to {FIXTURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
