"""Tests for Flex-Alarm delivery senders."""

import pytest

from strompilot.flexalarm.models import Alert
from strompilot.flexalarm.senders import (
    LoggingSender,
    SendError,
    SmtpSender,
    WebhookSender,
    senders_for,
)


def alert() -> Alert:
    """Bare alert for sender tests."""
    from datetime import UTC, datetime

    return Alert(
        id=1,
        household_id="hh1",
        dedup_key="k1",
        kind="cheap_window",
        title="billig",
        body="Text",
        status="held",
        channel=None,
        reason="ok",
        created_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )


def test_logging_sender_always_succeeds() -> None:
    sender = LoggingSender()
    assert sender.channel == "log"
    sender.send(alert())


def test_webhook_posts_title_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    seen: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

    def fake_post(url: str, json: dict[str, object], timeout: float) -> FakeResponse:
        del timeout
        seen["url"] = url
        seen["json"] = json
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    sender = WebhookSender("https://push.example/hook")
    sender.send(alert())
    assert seen["url"] == "https://push.example/hook"
    payload = seen["json"]
    assert isinstance(payload, dict)
    assert payload["title"] == "billig"
    assert payload["body"] == "Text"


def test_webhook_rejects_plain_http() -> None:
    with pytest.raises(ValueError, match="https"):
        WebhookSender("http://push.example/hook")


def test_webhook_failure_raises_send_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    class FakeResponse:
        status_code = 500

    def fake_post(url: str, json: dict[str, object], timeout: float) -> FakeResponse:
        del url, json, timeout
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(SendError, match="webhook"):
        WebhookSender("https://push.example/hook").send(alert())


def test_smtp_sends_a_german_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    import smtplib

    seen: dict[str, object] = {}

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            del timeout
            seen["host"] = host
            seen["port"] = port

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def starttls(self) -> None:
            seen["tls"] = True

        def login(self, user: str, password: str) -> None:
            seen["user"] = (user, password)

        def send_message(self, message: object) -> None:
            seen["message"] = message

    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    sender = SmtpSender(
        host="smtp.example",
        port=587,
        username="user",
        password="secret",
        sender="strom@example",
        recipient="hh@example",
    )
    sender.send(alert())
    assert seen["host"] == "smtp.example"
    assert seen["tls"] is True
    from email.message import EmailMessage

    message = seen["message"]
    assert isinstance(message, EmailMessage)
    assert message["To"] == "hh@example"
    assert "billig" in str(message["Subject"])
    assert "Text" in str(message.get_content())


def test_smtp_failure_raises_send_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import smtplib

    class FakeSmtp:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def starttls(self) -> None:
            raise smtplib.SMTPException("tls down")

    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    sender = SmtpSender(
        host="smtp.example",
        port=587,
        username="u",
        password="p",
        sender="a@b.c",
        recipient="d@e.f",
    )
    with pytest.raises(SendError, match="smtp"):
        sender.send(alert())


def test_senders_for_wires_prefs_and_env() -> None:
    prefs = {
        "alert_webhook": "https://push.example/hook",
        "alert_email": "hh@example",
    }
    env = {
        "FLEXALARM_SMTP_HOST": "smtp.example",
        "FLEXALARM_SMTP_USER": "u",
        "FLEXALARM_SMTP_PASS": "p",
        "FLEXALARM_SMTP_FROM": "a@b.c",
    }
    senders = senders_for(prefs, env)
    assert [sender.channel for sender in senders] == ["webhook", "smtp", "log"]


def test_senders_for_falls_back_to_log_only() -> None:
    senders = senders_for({}, {})
    assert [sender.channel for sender in senders] == ["log"]
