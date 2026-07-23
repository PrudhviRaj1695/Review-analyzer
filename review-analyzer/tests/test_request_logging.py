"""Verify the request-logging middleware: one line per request, slow ones stand out."""

import logging

from app.settings import settings


def test_request_logged_with_method_path_status_and_duration(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.main"):
        response = client.get("/")

    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == "app.main"]
    assert len(records) == 1, "exactly one log line per request"
    assert records[0].levelno == logging.INFO
    message = records[0].getMessage()
    assert message.startswith("GET / -> 200 ("), message
    assert message.endswith("ms)"), message


def test_slow_request_logs_at_warning(client, caplog, monkeypatch):
    monkeypatch.setattr(settings, "http_slow_request_seconds", 0)

    with caplog.at_level(logging.INFO, logger="app.main"):
        response = client.get("/")

    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == "app.main"]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
