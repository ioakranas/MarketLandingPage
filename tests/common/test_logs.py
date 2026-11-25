"""Log formatting: JSON for log platforms, text for developers, request id on every line."""

import json
import logging

from common.logs import JsonFormatter, TextFormatter, request_id_var


def make_record(message="login.failed", level=logging.WARNING, exc_info=None, **extra):
    record = logging.getLogger("audit").makeRecord(
        "audit", level, __file__, 1, message, (), exc_info, extra=extra
    )
    return record


def test_every_record_carries_the_current_request_id():
    token = request_id_var.set("req-12345678")
    try:
        record = logging.getLogger("any").makeRecord("any", logging.INFO, __file__, 1, "x", (), None)
    finally:
        request_id_var.reset(token)

    assert record.request_id == "req-12345678"


def test_outside_a_request_the_id_is_none():
    record = logging.getLogger("any").makeRecord("any", logging.INFO, __file__, 1, "x", (), None)
    assert record.request_id is None


def test_json_line_has_standard_and_extra_fields():
    record = make_record(event="login.failed", reason="wrong_password", user_id=7, ip="127.0.0.1")
    record.request_id = "abc12345"

    entry = json.loads(JsonFormatter().format(record))

    assert entry.pop("time").endswith("+00:00")  # UTC, ISO 8601
    assert entry == {
        "level": "WARNING",
        "logger": "audit",
        "message": "login.failed",
        "event": "login.failed",
        "reason": "wrong_password",
        "user_id": 7,
        "ip": "127.0.0.1",
        "request_id": "abc12345",
    }


def test_json_includes_the_exception_and_survives_odd_values():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = make_record(level=logging.ERROR, exc_info=sys.exc_info(), value=object())

    entry = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in entry["exception"]
    assert entry["value"].startswith("<object object")  # not JSON-native: stringified


def test_json_leaves_out_djangos_request_object():
    record = make_record(request=object(), status_code=404)
    entry = json.loads(JsonFormatter().format(record))
    assert "request" not in entry
    assert entry["status_code"] == 404


def test_text_line_is_readable():
    record = make_record(event="login.failed", reason="wrong_password")
    record.request_id = "abc12345"

    line = TextFormatter().format(record)

    assert " WARNING audit [abc12345] login.failed event=login.failed reason=wrong_password" in line


def test_text_line_without_request_or_extras():
    record = logging.getLogger("x").makeRecord("x", logging.INFO, __file__, 1, "started", (), None)
    assert TextFormatter().format(record).endswith(" INFO x [-] started")


def test_installing_the_request_id_factory_twice_is_harmless():
    from common.logs import install_request_id_factory

    installed = logging.getLogRecordFactory()
    install_request_id_factory()
    assert logging.getLogRecordFactory() is installed  # not wrapped a second time
