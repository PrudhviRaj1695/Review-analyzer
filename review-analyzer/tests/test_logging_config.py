import logging

from app.logging_config import configure_logging


def test_configure_logging_uses_jsonish_formatter():
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    configure_logging()

    assert root_logger.handlers, "logging should register at least one handler"
    formatter = root_logger.handlers[0].formatter
    assert formatter is not None

    record = logging.LogRecord(
        name="demo.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    rendered = formatter.format(record)

    assert '"timestamp"' in rendered
    assert '"level": "INFO"' in rendered
    assert '"logger": "demo.logger"' in rendered
    assert '"message": "hello world"' in rendered
