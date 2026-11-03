"""Seed one rich demo household through the real API.

Signs in as the demo email over the public magic-link flow, then builds
a complete showcase case: household prefs (devices, quiet hours, annual
use); a full plan run that pauses, gets approved, and collects feedback;
two meter photos with serials, photos, and calibration; plus one watcher
pass. Every row is created through the public endpoints, so the data is
exactly what real usage produces. Run from the repo root with the
backend up in log-mailer mode:

    .venv\\Scripts\\python.exe scripts/seed_demo.py

Options: --api, --email, --lang, --web (for the printed links).
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
        try:
            detail = client.get(f"/plan/{thread_id}").json()
        except (
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.ReadTimeout,
        ):
            time.sleep(5)
            continue
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
    parser.add_argument("--email", default="demo@example.de")
    parser.add_argument("--lang", default="en", choices=["de", "en"])
    args = parser.parse_args()
    client = httpx.Client(base_url=args.api, timeout=TIMEOUT)

    requested = client.post("/auth/request-link", json={"email": args.email})
    requested.raise_for_status()
    dev_link = requested.json().get("dev_link")
    if not dev_link:
        raise SystemExit(
            "no dev link returned: seed needs the log mailer "
            "(STROMPILOT_MAILER unset or log)"
        )
    token = dev_link.split("token=")[1]
    verified = client.get(f"/auth/verify?token={token}")
    verified.raise_for_status()
    household = verified.json()["household_id"]
    print(f"signed in as {args.email} in household {household}")

    prefs = {
        "devices": ["Waschmaschine", "Geschirrspueler", "E-Auto"],
        "quiet_hours": {"start": "22:00", "end": "06:00"},
        "annual_kwh": 3500,
    }
    for key, value in prefs.items():
        stored = client.put(
            f"/memory/preferences/{key}?household_id={household}",
            json={"value": value},
        )
        stored.raise_for_status()
    print(f"household prefs stored: {', '.join(prefs)}")

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

    ground_truth = {"meter_clean.png": 4217.3, "meter_obis.png": 12893.0}
    for name, truth in ground_truth.items():
        with (FIXTURES / name).open("rb") as photo:
            uploaded = client.post(
                f"/meter/readings?household_id={household}&keep_photo=true",
                files={"file": (name, photo, "image/png")},
            )
        uploaded.raise_for_status()
        reading = uploaded.json()
        confirmed = client.post(
            f"/meter/readings/{reading['id']}/confirm?household_id={household}",
            json={"lang": args.lang, "corrected_value_kwh": truth},
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
