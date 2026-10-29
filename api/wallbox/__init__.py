"""Wallbox simulator: its own program behind an MCP server."""

from .sim import HARDWARE_MAX_KW, Sim, SimError

__all__ = ["HARDWARE_MAX_KW", "Sim", "SimError"]
