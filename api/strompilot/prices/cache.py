"""Disk cache for price series plus the fair-use fetch log."""

import json
import os
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel

from strompilot.prices.models import PriceSeries


class CachedEntry(BaseModel):
    """One cached day with its source and fetch time."""

    source: str
    fetched_at: datetime
    series: PriceSeries


class DiskCache:
    """JSON files per day plus one fetch log, all under one directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)

    def _series_path(self, target: date) -> Path:
        return self._directory / f"{target.isoformat()}.json"

    def _fetches_path(self) -> Path:
        return self._directory / "fetches.json"

    def read(self, target: date) -> CachedEntry | None:
        """Return the cached entry for a day, or None when absent or corrupt."""
        path = self._series_path(target)
        if not path.exists():
            return None
        try:
            return CachedEntry.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def write(
        self, target: date, series: PriceSeries, source: str, fetched_at: datetime
    ) -> None:
        """Store one day of prices with its source and fetch time."""
        entry = CachedEntry(source=source, fetched_at=fetched_at, series=series)
        self._write_text_atomic(self._series_path(target), entry.model_dump_json())

    def last_fetch(self, source: str) -> date | None:
        """Return the last day a live fetch ran for a source, if any."""
        raw = self._read_fetch_log()
        value = raw.get(source)
        return date.fromisoformat(value) if value else None

    def mark_fetched(self, source: str, day: date) -> None:
        """Record that a live fetch ran for a source on a day."""
        raw = self._read_fetch_log()
        raw[source] = day.isoformat()
        self._write_text_atomic(self._fetches_path(), json.dumps(raw, indent=2))

    def _read_fetch_log(self) -> dict[str, str]:
        """Return the fetch log, treating a missing or corrupt file as empty."""
        path = self._fetches_path()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        """Write a file atomically so a crash never leaves half a file."""
        tmp_path = path.with_name(path.name + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
