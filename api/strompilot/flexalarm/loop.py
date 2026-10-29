"""Watcher loop: scan, judge, dedup, hold or deliver."""

import os
from datetime import datetime

from strompilot.llm.types import ChatRouter
from strompilot.memory.store import MemoryStore
from strompilot.prices.models import PriceSeries

from .compose import compose
from .models import Alert, WatchReport
from .quiet import is_quiet, parse_quiet_hours
from .senders import Sender, SendError, senders_for
from .store import AlertStore, dedup_key
from .triage import judge
from .watch import scan_windows


def _devices(memory: MemoryStore, household_id: str) -> list[str]:
    """Read the household device names, tolerating missing prefs."""
    devices = memory.get_preference(household_id, "devices")
    if not isinstance(devices, list):
        return []
    return [str(name) for name in devices]


def _deliver(alert: Alert, senders: list[Sender]) -> tuple[str | None, str | None]:
    """Try each sender in order, returning channel or error."""
    errors: list[str] = []
    for sender in senders:
        try:
            sender.send(alert)
        except SendError as exc:
            errors.append(f"{sender.channel}: {exc}")
            continue
        return sender.channel, None
    return None, "; ".join(errors)


def run_once(
    household_id: str,
    series: PriceSeries,
    memory: MemoryStore,
    alerts: AlertStore,
    router: ChatRouter,
    senders: list[Sender] | None,
    now: datetime,
) -> WatchReport:
    """Run one watcher pass over one household and one price day."""
    active = (
        senders
        if senders is not None
        else senders_for(
            {pref.key: pref.value for pref in memory.list_preferences(household_id)},
            os.environ,
        )
    )
    quiet = parse_quiet_hours(memory.get_preference(household_id, "quiet_hours"))
    release = release_due(
        household_id=household_id,
        memory=memory,
        alerts=alerts,
        senders=active,
        now=now,
    )
    devices = _devices(memory, household_id)
    known = alerts.known_keys(household_id)
    recent = [alert.title for alert in alerts.list_alerts(household_id, limit=5)]
    candidates = scan_windows(series)
    fired = held = delivered = skipped = duplicates = 0
    errors: list[str] = []
    for candidate in candidates:
        key = dedup_key(household_id, candidate)
        if key in known:
            duplicates += 1
            continue
        verdict = judge(candidate, devices, recent, router)
        if not verdict.fire:
            skipped += 1
            continue
        title, body = compose(candidate, verdict)
        if is_quiet(now, quiet):
            stored = alerts.record(
                household_id=household_id,
                dedup_key=key,
                kind=candidate.kind,
                title=title,
                body=body,
                status="held",
                channel=None,
                reason=verdict.reason,
            )
            if stored is None:
                duplicates += 1
                continue
            known.add(key)
            fired += 1
            held += 1
            continue
        stored = alerts.record(
            household_id=household_id,
            dedup_key=key,
            kind=candidate.kind,
            title=title,
            body=body,
            status="held",
            channel=None,
            reason=verdict.reason,
        )
        if stored is None:
            duplicates += 1
            continue
        known.add(key)
        fired += 1
        channel, error = _deliver(stored, active)
        if channel is None:
            alerts.set_status(stored.id, "failed", None)
            errors.append(f"{key}: {error}")
        else:
            alerts.set_status(stored.id, "delivered", channel)
            delivered += 1
    return WatchReport(
        household_id=household_id,
        day=series.date,
        candidates=len(candidates),
        fired=fired,
        held=held,
        delivered=delivered,
        released=release["delivered"],
        skipped=skipped,
        duplicates=duplicates,
        errors=errors,
    )


def release_due(
    household_id: str,
    memory: MemoryStore,
    alerts: AlertStore,
    senders: list[Sender],
    now: datetime,
) -> dict[str, int]:
    """Deliver held alerts once quiet hours have passed."""
    quiet = parse_quiet_hours(memory.get_preference(household_id, "quiet_hours"))
    if is_quiet(now, quiet):
        return {"delivered": 0, "failed": 0}
    delivered = failed = 0
    for alert in alerts.held(household_id):
        channel, _ = _deliver(alert, senders)
        if channel is None:
            alerts.set_status(alert.id, "failed", None)
            failed += 1
        else:
            alerts.set_status(alert.id, "delivered", channel)
            delivered += 1
    return {"delivered": delivered, "failed": failed}


def run_all(
    series: PriceSeries,
    memory: MemoryStore,
    alerts: AlertStore,
    router: ChatRouter,
    senders: list[Sender] | None,
    now: datetime,
) -> list[WatchReport]:
    """Run one watcher pass for every known household."""
    return [
        run_once(
            household_id=household_id,
            series=series,
            memory=memory,
            alerts=alerts,
            router=router,
            senders=senders,
            now=now,
        )
        for household_id in memory.list_households()
    ]
