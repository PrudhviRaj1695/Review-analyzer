import contextvars
import json
import logging
import os
from datetime import datetime, timezone

_CONFIGURED = False

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class RequestIdFilter(logging.Filter):
    """Stamp every log record with the current request's id, if any."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Format log records as compact JSON objects with key context fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int | None = None) -> logging.Logger:
    """Configure root logging once for the application and scripts.

    level defaults to the LOG_LEVEL env var (e.g. LOG_LEVEL=DEBUG), falling
    back to INFO if unset or invalid.
    """
    global _CONFIGURED

    root_logger = logging.getLogger()
    if _CONFIGURED and root_logger.handlers:
        return root_logger

    if level is None:
        level = getattr(
            logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO
        )

    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root_logger.addHandler(handler)
    root_logger.propagate = False

    _CONFIGURED = True
    return root_logger
