"""Typed API contract stub shared with the frontend.

The TypeScript mirror lives in web/lib/contract.ts and pins the same
CONTRACT_VERSION. Both sides assert the pinned value in their test suites.
"""

from pydantic import BaseModel

CONTRACT_VERSION = "0.7.0"


class HealthResponse(BaseModel):
    """Payload returned by GET /health."""

    status: str
    service: str
    contract_version: str
