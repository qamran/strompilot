"""Wallbox MCP client: one spawned call per tool, state on disk."""

import asyncio
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

BERLIN = ZoneInfo("Europe/Berlin")
_CLOCK = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

Caller = Callable[[str, dict[str, Any]], dict[str, Any]]


class WallboxError(Exception):
    """Any wallbox failure: transport, sim refusal, or bad payload."""


@dataclass(frozen=True)
class ChargeProgram:
    """One programmed charge window in ISO times."""

    start: str
    end: str
    max_kw: float


@dataclass(frozen=True)
class WallboxStatus:
    """Parsed wallbox status."""

    plugged: bool
    charging: bool
    power_kw: float
    max_kw: float
    session_kwh: float
    total_kwh: float
    sim_now: str
    program: ChargeProgram | None


def _parse_status(payload: dict[str, Any]) -> WallboxStatus:
    """Parse one status payload, failing loudly on bad shapes."""
    try:
        program_raw = payload["program"]
        program = (
            None
            if program_raw is None
            else ChargeProgram(
                start=str(program_raw["start"]),
                end=str(program_raw["end"]),
                max_kw=float(program_raw["max_kw"]),
            )
        )
        return WallboxStatus(
            plugged=bool(payload["plugged"]),
            charging=bool(payload["charging"]),
            power_kw=float(payload["power_kw"]),
            max_kw=float(payload["max_kw"]),
            session_kwh=float(payload["session_kwh"]),
            total_kwh=float(payload["total_kwh"]),
            sim_now=str(payload["sim_now"]),
            program=program,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WallboxError(f"bad status payload: {exc}") from exc


def _payload(result: types.CallToolResult) -> dict[str, Any]:
    """Read one tool result, structured first, JSON text second."""
    if result.is_error:
        texts = [
            block.text
            for block in result.content
            if isinstance(block, types.TextContent)
        ]
        raise WallboxError(f"sim refused: {'; '.join(texts) or 'unknown error'}")
    if isinstance(result.structured_content, dict):
        payload = dict(result.structured_content)
    else:
        payload = _text_payload(result)
    if "error" in payload:
        raise WallboxError(f"sim refused: {payload['error']}")
    return payload


def _text_payload(result: types.CallToolResult) -> dict[str, Any]:
    """Parse the first text block of one tool result as JSON."""
    for block in result.content:
        if isinstance(block, types.TextContent):
            try:
                parsed: Any = json.loads(block.text)
            except ValueError as exc:
                raise WallboxError(f"bad tool payload: {exc}") from exc
            if not isinstance(parsed, dict):
                raise WallboxError("bad tool payload: not an object")
            return parsed
    raise WallboxError("bad tool payload: empty result")


class WallboxDriver(Protocol):
    """One programmable wallbox, real client or fake."""

    def status(self) -> WallboxStatus: ...

    def program(self, start_iso: str, end_iso: str, max_kw: float) -> WallboxStatus: ...


def iso_window(day: date, start: str, end: str) -> tuple[str, str]:
    """Convert one HH:MM window to ISO times, rolling overnight ends."""
    start_match = _CLOCK.match(start)
    end_match = _CLOCK.match(end)
    if start_match is None or end_match is None:
        raise WallboxError(f"bad clock times: {start!r}, {end!r}")
    start_dt = datetime(
        day.year,
        day.month,
        day.day,
        int(start_match.group(1)),
        int(start_match.group(2)),
        tzinfo=BERLIN,
    )
    end_dt = datetime(
        day.year,
        day.month,
        day.day,
        int(end_match.group(1)),
        int(end_match.group(2)),
        tzinfo=BERLIN,
    )
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt.isoformat(), end_dt.isoformat()


class WallboxClient:
    """Sync wrapper over spawn-per-call MCP tool calls.

    Every call spawns the simulator, which loads its JSON state,
    acts, saves, and exits. Slow per call, crash-safe always:
    wallbox calls are rare, so simplicity wins over session speed.
    """

    def __init__(
        self,
        state_path: Path | None = None,
        command: list[str] | None = None,
        timeout: float = 60.0,
        caller: Caller | None = None,
    ) -> None:
        self._state_path = state_path
        self._command = command or [sys.executable, "-m", "wallbox.server"]
        self._timeout = timeout
        self._caller = caller or self._spawn_call

    def _spawn_call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run one tool through a fresh simulator process."""
        env = dict(os.environ)
        if self._state_path is not None:
            env["WALLBOX_STATE"] = str(self._state_path)
        params = StdioServerParameters(
            command=self._command[0], args=self._command[1:], env=env
        )

        async def once() -> types.CallToolResult:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, args)
                    assert isinstance(result, types.CallToolResult)
                    return result

        try:
            result = asyncio.run(asyncio.wait_for(once(), self._timeout))
        except Exception as exc:
            raise WallboxError(f"wallbox call failed: {exc}") from exc
        # Parsed here, not inside once(): anyio wraps exceptions raised
        # inside the session block in ExceptionGroups, which would bury
        # the sim's refusal message.
        return _payload(result)

    def status(self) -> WallboxStatus:
        """Report plug, charging, power, energy, clock, and program."""
        return _parse_status(self._caller("get_status", {}))

    def plug(self) -> WallboxStatus:
        """Plug the car in."""
        return _parse_status(self._caller("plug", {}))

    def unplug(self) -> WallboxStatus:
        """Unplug the car."""
        return _parse_status(self._caller("unplug", {}))

    def start(self, max_kw: float) -> WallboxStatus:
        """Charge immediately at up to max_kw."""
        return _parse_status(self._caller("start_now", {"max_kw": max_kw}))

    def stop(self) -> WallboxStatus:
        """Stop charging and clear programs."""
        return _parse_status(self._caller("stop_now", {}))

    def program(self, start_iso: str, end_iso: str, max_kw: float) -> WallboxStatus:
        """Program one charge window in ISO times."""
        return _parse_status(
            self._caller(
                "program_charge",
                {"start_iso": start_iso, "end_iso": end_iso, "max_kw": max_kw},
            )
        )

    def program_window(
        self, day: date, start: str, end: str, max_kw: float
    ) -> WallboxStatus:
        """Program one HH:MM window, rolling overnight ends a day forward."""
        start_iso, end_iso = iso_window(day, start, end)
        return self.program(start_iso, end_iso, max_kw)

    def advance(self, minutes: int) -> WallboxStatus:
        """Move the simulator clock. Simulator only."""
        return _parse_status(self._caller("advance_clock", {"minutes": minutes}))
