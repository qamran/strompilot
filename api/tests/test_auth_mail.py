"""Tests for the auth mailers: log default plus SMTP option."""

import logging

import pytest

from strompilot.auth.mail import LogMailer, SmtpMailer, mailer_from_env


def test_log_mailer_records_the_link(caplog: pytest.LogCaptureFixture) -> None:
    """The log mailer never sends mail but always records the link."""
    with caplog.at_level(logging.INFO, logger="strompilot.auth.mail"):
        LogMailer().send("lena@example.de", "https://app/verify?token=abc")
    assert "https://app/verify?token=abc" in caplog.text
    assert "lena@example.de" in caplog.text


def test_mailer_defaults_to_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without configuration the mailer logs instead of sending."""
    monkeypatch.delenv("STROMPILOT_MAILER", raising=False)
    assert isinstance(mailer_from_env(), LogMailer)


def test_mailer_selects_smtp_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """STROMPILOT_MAILER=smtp selects the SMTP mailer with its settings."""
    monkeypatch.setenv("STROMPILOT_MAILER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "mail.example.de")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "bot@example.de")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "strompilot@example.de")
    mailer = mailer_from_env()
    assert isinstance(mailer, SmtpMailer)
    assert mailer.host == "mail.example.de"
    with pytest.raises(ValueError, match="SMTP_HOST"):
        monkeypatch.delenv("SMTP_HOST")
        mailer_from_env()


class _FakeSmtp:
    """Minimal smtplib stand-in that records one send."""

    last: "_FakeSmtp | None" = None

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sent: tuple[str, str, str] | None = None
        _FakeSmtp.last = self

    def __enter__(self) -> "_FakeSmtp":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def starttls(self) -> None:
        return None

    def login(self, user: str, password: str) -> None:
        self.user = user
        self.password = password

    def sendmail(self, sender: str, recipient: str, message: str) -> None:
        self.sent = (sender, recipient, message)


def test_smtp_mailer_sends_the_link(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SMTP mailer delivers the link to the right recipient."""
    import smtplib

    monkeypatch.setattr(smtplib, "SMTP", _FakeSmtp)
    mailer = SmtpMailer(
        host="mail.example.de",
        port=587,
        user="bot@example.de",
        password="secret",
        sender="strompilot@example.de",
    )
    mailer.send("lena@example.de", "https://app/verify?token=abc")
    assert _FakeSmtp.last is not None
    assert _FakeSmtp.last.sent is not None
    sender, recipient, message = _FakeSmtp.last.sent
    assert sender == "strompilot@example.de"
    assert recipient == "lena@example.de"
    assert "https://app/verify?token=abc" in message
