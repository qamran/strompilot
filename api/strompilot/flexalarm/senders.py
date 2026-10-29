"""Delivery senders: webhook push, SMTP mail, and the log fallback."""

import smtplib
from collections.abc import Mapping
from email.message import EmailMessage
from email.utils import formatdate
from typing import Any, Protocol

import httpx

from .models import Alert


class SendError(Exception):
    """One delivery attempt failed and the next sender is up."""


class Sender(Protocol):
    """One delivery path for fired alerts."""

    channel: str

    def send(self, alert: Alert) -> None: ...


class LoggingSender:
    """Fallback path: the alert is stored, delivery needs no network."""

    channel = "log"

    def send(self, alert: Alert) -> None:
        """Accept every alert; the store is the record."""
        del alert


class WebhookSender:
    """Push path: POST the alert to a household webhook URL."""

    channel = "webhook"

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        if not url.startswith("https://"):
            raise ValueError("webhook url must use https")
        self._url = url
        self._timeout = timeout

    def send(self, alert: Alert) -> None:
        """POST title and body, raising SendError on any failure."""
        try:
            response = httpx.post(
                self._url,
                json={
                    "title": alert.title,
                    "body": alert.body,
                    "kind": alert.kind,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise SendError(f"webhook failed: {exc}") from exc
        if response.status_code >= 300:
            raise SendError(f"webhook failed: status {response.status_code}")


class SmtpSender:
    """Mail path: send the alert through the household SMTP relay."""

    channel = "smtp"

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        recipient: str,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._recipient = recipient
        self._timeout = timeout

    def send(self, alert: Alert) -> None:
        """Send one plain-text mail, raising SendError on any failure."""
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = self._recipient
        message["Subject"] = f"Strompilot: {alert.title}"
        message["Date"] = formatdate(localtime=True)
        message.set_content(alert.body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                smtp.starttls()
                smtp.login(self._username, self._password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            raise SendError(f"smtp failed: {exc}") from exc


def senders_for(prefs: Mapping[str, Any], env: Mapping[str, str]) -> list[Sender]:
    """Wire the household's channels, always ending in the log fallback."""
    senders: list[Sender] = []
    webhook = prefs.get("alert_webhook")
    if isinstance(webhook, str) and webhook.startswith("https://"):
        senders.append(WebhookSender(webhook))
    email = prefs.get("alert_email")
    host = env.get("FLEXALARM_SMTP_HOST", "")
    user = env.get("FLEXALARM_SMTP_USER", "")
    password = env.get("FLEXALARM_SMTP_PASS", "")
    sender = env.get("FLEXALARM_SMTP_FROM", "")
    if isinstance(email, str) and email and host and user and password and sender:
        try:
            port = int(env.get("FLEXALARM_SMTP_PORT", "587"))
        except ValueError:
            port = 587
        senders.append(
            SmtpSender(
                host=host,
                port=port,
                username=user,
                password=password,
                sender=sender,
                recipient=email,
            )
        )
    senders.append(LoggingSender())
    return senders
