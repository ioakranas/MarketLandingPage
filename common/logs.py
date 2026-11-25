"""Structured logging: JSON or text lines, every line tagged with its request id.

Comparable to Logback + MDC + logstash-logback-encoder in Spring:
- request_id_var holds the current request's id (a ContextVar: correct per request
  and per thread/async task); the log record factory copies it onto every record,
  from our code, Django or any library.
- JsonFormatter writes one JSON object per line for log platforms (ELK, Datadog, SIEM).
- TextFormatter writes the same content readably for a developer's terminal.
Extra fields passed with logger.info(..., extra={...}) become JSON keys / key=value pairs.
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything else on a record is an "extra" field.
_STANDARD_ATTRIBUTES = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}
# Extras Django attaches that are objects, not data (the path is in the access log).
_IGNORED_EXTRAS = {"request", "server_time"}


def install_request_id_factory() -> None:
    """Tag every log record with the current request id (None outside requests)."""
    previous = logging.getLogRecordFactory()
    if getattr(previous, "adds_request_id", False):
        return  # already installed

    def factory(*args, **kwargs) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        record.request_id = request_id_var.get()
        return record

    factory.adds_request_id = True
    logging.setLogRecordFactory(factory)


def extra_fields(record: logging.LogRecord) -> dict:
    return {
        key: value
        for key, value in vars(record).items()
        if key not in _STANDARD_ATTRIBUTES and key not in _IGNORED_EXTRAS
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **extra_fields(record),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """2026-11-25 18:02:11 WARNING audit [3f2c9a...] login.failed reason=wrong_password"""

    def __init__(self):
        super().__init__("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        fields = extra_fields(record)
        record.request_id = fields.pop("request_id", None) or "-"
        line = super().format(record)
        pairs = " ".join(f"{key}={value}" for key, value in fields.items())
        return f"{line} {pairs}" if pairs else line
