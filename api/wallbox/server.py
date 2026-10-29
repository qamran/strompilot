"""Wallbox MCP server: stdio tools over the simulator."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer

from wallbox.sim import Sim, SimError

server = MCPServer("strompilot-wallbox")


def _guarded(action: str, *args: object) -> dict[str, Any]:
    """Run one sim action, returning an error payload instead of raising.

    Tool exceptions kill the stdio session in MCP 2.x, so the server
    reports refusals as data and the client raises them as WallboxError.
    """
    try:
        method = getattr(_sim(), action)
        result = method(*args)
        assert isinstance(result, dict)
        return result
    except SimError as exc:
        return {"error": str(exc)}


def _state_path() -> Path:
    """Return the sim state file, honoring WALLBOX_STATE."""
    override = os.environ.get("WALLBOX_STATE")
    if override:
        return Path(override)
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data" / "wallbox.json"


def _sim() -> Sim:
    """Load the simulator, starting its clock at now when fresh."""
    return Sim.load(_state_path(), datetime.now(ZoneInfo("Europe/Berlin")))


@server.tool()
def get_status() -> dict[str, Any]:
    """Report plug, charging, power, energy, clock, and program."""
    return _guarded("status")


@server.tool()
def plug() -> dict[str, Any]:
    """Plug the car into the wallbox."""
    return _guarded("plug")


@server.tool()
def unplug() -> dict[str, Any]:
    """Unplug the car, ending any session."""
    return _guarded("unplug")


@server.tool()
def start_now(max_kw: float) -> dict[str, Any]:
    """Charge immediately at up to max_kw."""
    return _guarded("start_now", max_kw)


@server.tool()
def stop_now() -> dict[str, Any]:
    """Stop charging and clear manual mode plus any program."""
    return _guarded("stop_now")


@server.tool()
def program_charge(start_iso: str, end_iso: str, max_kw: float) -> dict[str, Any]:
    """Program one charge window; the clock drives the rest."""
    return _guarded("program_charge", start_iso, end_iso, max_kw)


@server.tool()
def advance_clock(minutes: int) -> dict[str, Any]:
    """Move the simulator clock, integrating energy. Simulator only."""
    return _guarded("advance_clock", minutes)


def main() -> None:
    """Serve wallbox tools over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
