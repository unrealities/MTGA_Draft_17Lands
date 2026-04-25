import pytest
import logging
from src.logger import create_logger, CustomFormatter


def test_create_logger():
    logger = create_logger()
    assert logger.name == "debug_log"
    assert logger.level == logging.DEBUG


def test_custom_formatter():
    formatter = CustomFormatter()
    record = logging.LogRecord("name", logging.ERROR, "pathname", 1, "msg", None, None)
    formatted = formatter.format(record)
    assert "msg" in formatted
    assert "ERROR" in formatted

    record_info = logging.LogRecord(
        "name", logging.INFO, "pathname", 1, "info msg", None, None
    )
    formatted_info = formatter.format(record_info)
    assert "info msg" in formatted_info
    assert "INFO" in formatted_info
