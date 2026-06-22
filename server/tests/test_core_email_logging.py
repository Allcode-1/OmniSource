import json
import logging
import sys

import pytest

from app.core import email as email_module
from app.core import logging as logging_module


class _FakeSMTP:
    def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.ehlo_calls = 0
        self.started_tls = False
        self.logged_in = None
        self.sent = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        self.ehlo_calls += 1

    def starttls(self, context=None) -> None:
        self.started_tls = True

    def login(self, user: str, password: str) -> None:
        self.logged_in = (user, password)

    def send_message(self, message) -> None:
        self.sent = message


def test_send_reset_password_email_uses_smtp(monkeypatch) -> None:
    fake_smtp = _FakeSMTP("smtp.test", 2525)

    def fake_smtp_factory():
        return fake_smtp

    monkeypatch.setattr(email_module, "_create_smtp_client", fake_smtp_factory)
    email_module.send_reset_password_email("user@test.dev", "abc-token")

    assert fake_smtp.started_tls is True
    assert fake_smtp.ehlo_calls == 2
    assert fake_smtp.logged_in == (
        email_module.settings.SMTP_USER,
        email_module.settings.SMTP_PASSWORD,
    )
    assert fake_smtp.sent is not None
    assert fake_smtp.sent["From"] == email_module.settings.EMAILS_FROM_EMAIL
    assert fake_smtp.sent["To"] == "user@test.dev"
    assert "abc-token" in fake_smtp.sent.as_string()


def test_send_reset_password_email_logs_exception_on_failure(monkeypatch) -> None:
    class _BrokenSMTP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self, context=None) -> None:
            raise RuntimeError("smtp failed")

    captured = {"called": False}

    def fake_exception(message: str, *args) -> None:
        captured["called"] = True
        assert "Error sending reset email" in message

    monkeypatch.setattr(email_module, "_create_smtp_client", _BrokenSMTP)
    monkeypatch.setattr(email_module.logger, "exception", fake_exception)

    with pytest.raises(RuntimeError, match="smtp failed"):
        email_module.send_reset_password_email("user@test.dev", "abc-token")
    assert captured["called"] is True


def test_create_smtp_client_prefers_ipv4(monkeypatch) -> None:
    captured = {}

    class _FakeIPv4SMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            captured.update(host=host, port=port, timeout=timeout)

    monkeypatch.setattr(email_module, "_IPv4SMTP", _FakeIPv4SMTP)
    monkeypatch.setattr(email_module.settings, "SMTP_FORCE_IPV4", True)

    client = email_module._create_smtp_client()

    assert isinstance(client, _FakeIPv4SMTP)
    assert captured == {
        "host": email_module.settings.SMTP_HOST,
        "port": email_module.settings.SMTP_PORT,
        "timeout": 15,
    }


def test_json_formatter_renders_extra_fields_and_exception() -> None:
    formatter = logging_module.JsonFormatter()

    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="something failed",
            args=(),
            exc_info=sys.exc_info(),
        )
        record.request_id = "r1"
        record.method = "GET"
        record.path = "/health"
        record.status = 500
        record.duration_ms = 12.5
        payload = json.loads(formatter.format(record))

    assert payload["logger"] == "app.test"
    assert payload["message"] == "something failed"
    assert payload["request_id"] == "r1"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status"] == 500
    assert payload["duration_ms"] == 12.5
    assert "exception" in payload


def test_configure_logging_calls_dict_config(monkeypatch) -> None:
    captured = {}

    def fake_dict_config(config: dict) -> None:
        captured["config"] = config

    monkeypatch.setattr(logging_module, "dictConfig", fake_dict_config)
    logging_module.configure_logging()

    config = captured["config"]
    assert config["version"] == 1
    assert "console" in config["handlers"]
    assert config["root"]["handlers"] == ["console"]


def test_get_logger_returns_named_logger() -> None:
    logger = logging_module.get_logger("custom.logger")
    assert logger.name == "custom.logger"
