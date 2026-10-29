"""On-camera demo: the agent charges the wallbox in the cheap window.

Loads tomorrow's day-ahead prices, finds the cheapest window, checks
the policy gates, programs the wallbox simulator over MCP, and ticks
the simulator clock through the charge. Prints every step.
"""

import argparse
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, "api")

from dotenv import load_dotenv
from strompilot.flexalarm.watch import scan_windows
from strompilot.prices.models import BERLIN
from strompilot.prices.service import get_day_ahead_prices
from strompilot.wallbox.client import WallboxClient, iso_window
from strompilot.wallbox.policy import ChargePolicy, authorize

load_dotenv(".env")

parser = argparse.ArgumentParser(description="Run the wallbox charge demo.")
parser.add_argument("--date", default=None, help="price day, YYYY-MM-DD")
parser.add_argument("--power", type=float, default=11.0, help="charge kW")
args = parser.parse_args()

root = Path(__file__).resolve().parent.parent
cache_dir = Path(os.environ.get("PRICE_CACHE_DIR", root / "data" / "prices"))
state_path = Path(os.environ.get("WALLBOX_STATE", root / "data" / "wallbox.json"))
target = (
    date.fromisoformat(args.date)
    if args.date
    else datetime.now(BERLIN).date() + timedelta(days=1)
)

series = get_day_ahead_prices(target, cache_dir, datetime.now(UTC))
cheap = next(c for c in scan_windows(series) if c.kind == "cheap_window")
print(f"day {target.isoformat()} ({series.source})")
print(f"cheap window {cheap.start}-{cheap.end} at {cheap.avg_ct_kwh:.2f} ct/kWh")

policy = ChargePolicy(max_kw=11.0)
start_iso, end_iso = iso_window(target, cheap.start, cheap.end)
denied = authorize(policy, start_iso, end_iso, 30.0)
print(
    f"gate check 30 kW: {'BLOCKED' if not denied.allowed else 'ALLOWED'} "
    f"({denied.reason})"
)
allowed = authorize(policy, start_iso, end_iso, args.power)
print(
    f"gate check {args.power} kW: {'ALLOWED' if allowed.allowed else 'BLOCKED'} "
    f"({allowed.reason})"
)
if not allowed.allowed:
    raise SystemExit("demo charge blocked by policy")

if state_path.exists():
    state_path.unlink()
client = WallboxClient(state_path=state_path)
client.plug()
client.program(start_iso, end_iso, args.power)
print(f"programmed {cheap.start}-{cheap.end} at {args.power} kW over MCP")

now = datetime.now(BERLIN)
start_dt = datetime.fromisoformat(start_iso)
lead_minutes = max(0, int((start_dt - now).total_seconds() // 60))
while lead_minutes > 0:
    hop = min(lead_minutes, 12 * 60)
    client.advance(hop)
    lead_minutes -= hop
    print(f"fast-forward {hop} min toward the window")
window_minutes = int((datetime.fromisoformat(end_iso) - start_dt).total_seconds() // 60)
step = 30
for done in range(0, window_minutes, step):
    client.advance(min(step, window_minutes - done))
    status = client.status()
    clock = datetime.fromisoformat(status.sim_now).strftime("%H:%M")
    print(
        f"{clock} charging={status.charging} "
        f"{status.power_kw:.1f} kW session={status.session_kwh:.2f} kWh"
    )
final = client.status()
print(f"DEMO COMPLETE: {final.session_kwh:.2f} kWh in {cheap.start}-{cheap.end}")
