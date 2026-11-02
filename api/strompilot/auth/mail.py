"""Auth mailers: log the magic link by default, SMTP when configured."""

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Protocol

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    """Delivers one magic link to one email address."""

    def send(self, email: str, link: str) -> None:
        """Send the sign-in link."""
        ...


class LogMailer:
    """Demo-safe mailer: records the link in the log, sends nothing."""

    def send(self, email: str, link: str) -> None:
        """Log the magic link instead of emailing it."""
        logger.info("magic link for %s: %s", email, link)


class SmtpMailer:
    """Real mailer: delivers the magic link over SMTP with TLS."""

    def __init__(
        self, host: str, port: int, user: str, password: str, sender: str
    ) -> None:
        self.host = host
        self.port = port
        self._user = user
        self._password = password
        self._sender = sender

    def send(self, email: str, link: str) -> None:
        """Send the magic link to one recipient."""
        message = EmailMessage()
        message["Subject"] = "Your Strompilot sign-in link"
        message["From"] = self._sender
        message["To"] = email
        message.set_content(
            f"Sign in to Strompilot with this link (valid 15 minutes):\n\n{link}\n"
        )
        with smtplib.SMTP(self.host, self.port) as client:
            client.starttls()
            client.login(self._user, self._password)
            client.sendmail(self._sender, email, message.as_string())


def mailer_from_env() -> Mailer:
    """Select the mailer from STROMPILOT_MAILER, defaulting to the log."""
    if os.environ.get("STROMPILOT_MAILER", "log").lower() != "smtp":
        return LogMailer()
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        raise ValueError("SMTP_HOST must be set for the smtp mailer")
    port = int(os.environ.get("SMTP_PORT", "587"))
    return SmtpMailer(
        host=host,
        port=port,
        user=os.environ.get("SMTP_USER", ""),
        password=os.environ.get("SMTP_PASSWORD", ""),
        sender=os.environ.get("SMTP_FROM", "strompilot@example.de"),
    )
