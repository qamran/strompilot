"""Seed one rich demo household through the real API.

Builds a complete showcase case for demo-haushalt: a full plan run that
pauses, gets approved, and collects feedback; two meter photos with
serials, photos, and calibration; plus one watcher pass. Every row is
created through the public endpoints, so the data is exactly what real
usage produces. Run from the repo root with the backend up:

    .venv\\Scripts\\python.exe scripts/seed_demo.py

Options: --api, --household, --lang, --web (for the printed links).
"""

import argparse
import sys
import time
from pathlib import Path

import httpx

FIXTURES = Path("api/tests/fixtures/meter")
PLAN_TEXT = (
    "Night shift, baby sleeps by 10 pm, car must be full by 07:00. "
    "Run the washing machine and the dishwasher overnight too."
)
TIMEOUT = httpx.Timeout(30.0, read=120.0)


def poll_plan(client: httpx.Client, thread_id: str) -> dict:
    """Wait until one plan run pauses, fails loudly on error."""
    deadline = time.time() + 600
    while time.time() < deadline:
        detail = client.get(f"/plan/{thread_id}").json()
        status = detail.get("status")
        if status in ("paused", "published"):
            return detail
        if status == "blocked":
            raise SystemExit(f"plan blocked: {detail.get('error')}")
        time.sleep(5)
    raise SystemExit("plan run timed out")


def main() -> None:
    """Seed the showcase case and print what landed where."""
    parser = argparse.ArgumentParser(description="Seed the demo household.")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--web", default="http://127.0.0.1:3100")
    parser.add_argument("--household", default="demo-haushalt")
    parser.add_argument("--lang", default="en", choices=["de", "en"])
    args = parser.parse_args()
    household = args.household
    client = httpx.Client(base_url=args.api, timeout=TIMEOUT)

    created = client.post(
        "/plan",
        json={"household_id": household, "text": PLAN_TEXT, "lang": args.lang},
    )
    created.raise_for_status()
    thread_id = created.json()["thread_id"]
    print(f"plan thread {thread_id} running...")
    detail = poll_plan(client, thread_id)
    slots = detail.get("schedule", [])
    print(
        f"plan paused with {len(slots)} slots, total {detail.get('total_cost_eur')} Euro"
    )

    decided = client.post(
        f"/approvals/threads/{thread_id}/decide", json={"approved": True}
    )
    decided.raise_for_status()
    print(f"plan approved: {decided.json().get('status')}")

    for slot in slots:
        reply = client.post(
            f"/feedback?household_id={household}",
            json={"device": slot["device"], "verdict": "good", "note": ""},
        )
        reply.raise_for_status()
    print(f"feedback stored for {len(slots)} devices")

    for name in ("meter_clean.png", "meter_obis.png"):
        with (FIXTURES / name).open("rb") as photo:
            uploaded = client.post(
                f"/meter/readings?household_id={household}&keep_photo=true",
                files={"file": (name, photo, "image/png")},
            )
        uploaded.raise_for_status()
        reading = uploaded.json()
        confirmed = client.post(
            f"/meter/readings/{reading['id']}/confirm?household_id={household}",
            json={"lang": args.lang},
        )
        confirmed.raise_for_status()
        print(
            f"reading #{reading['id']}: {reading['value_kwh']} kWh, "
            f"serial {reading['serial']}, photo kept"
        )

    watch = client.post(f"/flexalarm/watch?household_id={household}&lang={args.lang}")
    watch.raise_for_status()
    print(
        f"watch: fired={watch.json().get('fired')} skipped={watch.json().get('skipped')}"
    )

    print(f"see it at {args.web}/plan?thread={thread_id}")
    print(f"meter at {args.web}/meter, alarms at {args.web}/alarms")


if __name__ == "__main__":
    sys.exit(main())
