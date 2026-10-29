"""Run one Flex-Alarm watcher pass for cron.

Watches tomorrow's day-ahead prices by default (or --date), either for
one --household or for every known household. Needs META_API_KEY plus
BASETEN_API_KEY. Prints one JSON report per household.
"""

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, "api")

from dotenv import load_dotenv
from strompilot.agents.router import ModelRouter
from strompilot.flexalarm.loop import run_all, run_once
from strompilot.flexalarm.store import AlertStore
from strompilot.memory.store import MemoryStore
from strompilot.prices.models import BERLIN
from strompilot.prices.service import get_day_ahead_prices

load_dotenv(".env")

parser = argparse.ArgumentParser(description="Run one Flex-Alarm watcher pass.")
parser.add_argument("--household", default=None, help="one household id")
parser.add_argument("--date", default=None, help="price day, YYYY-MM-DD")
args = parser.parse_args()

try:
    meta_key = os.environ["META_API_KEY"]
    baseten_key = os.environ["BASETEN_API_KEY"]
except KeyError as exc:
    raise SystemExit(f"missing key: {exc}") from exc

root = Path(__file__).resolve().parent.parent
cache_dir = Path(os.environ.get("PRICE_CACHE_DIR", root / "data" / "prices"))
memory_db = Path(os.environ.get("MEMORY_DB", root / "data" / "memory.db"))
target = (
    date.fromisoformat(args.date)
    if args.date
    else datetime.now(BERLIN).date() + timedelta(days=1)
)

series = get_day_ahead_prices(target, cache_dir, datetime.now(UTC))
memory = MemoryStore(memory_db)
alerts = AlertStore(memory_db)
router = ModelRouter.from_keys(meta_key, baseten_key)
now = datetime.now(BERLIN)

if args.household:
    reports = [
        run_once(
            household_id=args.household,
            series=series,
            memory=memory,
            alerts=alerts,
            router=router,
            senders=None,
            now=now,
        )
    ]
else:
    reports = run_all(
        series=series,
        memory=memory,
        alerts=alerts,
        router=router,
        senders=None,
        now=now,
    )
for report in reports:
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False))
