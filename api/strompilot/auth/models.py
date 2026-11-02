"""Auth value objects: sessions, tokens, and the auth error."""

from dataclasses import dataclass
from datetime import datetime


class AuthError(Exception):
    """Raised when a token or session is missing, used, or expired."""


@dataclass(frozen=True)
class Session:
    """One signed-in household with its session expiry."""

    email: str
    household_id: str
    expires_at: datetime
