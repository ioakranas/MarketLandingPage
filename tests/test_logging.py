"""Request id, access log, audit events and the no-personal-data rule, through HTTP."""

import json
import logging
import re

import pytest
from rest_framework.test import APIClient

from common.logs import JsonFormatter
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

REGISTRATION = {
    "first_name": "Ioannis",
    "last_name": "Papadopoulos",
    "country": "GR",
    "phone_code": "30",
    "phone": "6912345678",
    "email": "ioannis@example.com",
    "password": PASSWORD,
    "terms": True,
}


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.INFO)
    return caplog


def events(caplog) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == "audit"]


def event(caplog, name) -> logging.LogRecord:
    [record] = [record for record in events(caplog) if record.event == name]
    return record


def register(client, **overrides):
    return client.post("/api/v1/registrations", {**REGISTRATION, **overrides}, format="json")


def log_in(client, email="ioannis@example.com", password=PASSWORD):
    return client.post("/api/v1/sessions", {"email": email, "password": password}, format="json")


# --- request id & access log -------------------------------------------------------


def test_every_response_has_a_request_id(client):
    response = client.get("/register")
    assert re.fullmatch(r"[0-9a-f]{32}", response["X-Request-ID"])


def test_a_well_formed_incoming_request_id_is_kept(client):
    response = client.get("/register", HTTP_X_REQUEST_ID="trace-0123456789")
    assert response["X-Request-ID"] == "trace-0123456789"


@pytest.mark.parametrize("incoming", ["short", "x" * 65, "evil\nline", "<script>alert(1)</script>"])
def test_malformed_incoming_request_ids_are_replaced(client, incoming):
    response = client.get("/register", HTTP_X_REQUEST_ID=incoming)
    assert re.fullmatch(r"[0-9a-f]{32}", response["X-Request-ID"])


def test_access_log_line_per_request_without_query_string(client, logs):
    response = client.get("/register?email=secret@example.com")

    [line] = [record for record in logs.records if record.name == "access"]
    assert line.getMessage() == "GET /register 200"
    assert (line.method, line.path, line.status) == ("GET", "/register", 200)
    assert line.duration_ms >= 0
    assert line.request_id == response["X-Request-ID"]
    assert "secret@example.com" not in logs.text


def test_static_files_get_a_request_id_but_no_access_line(client, logs):
    response = client.get("/static/css/main.css")

    assert response.status_code == 200
    assert re.fullmatch(r"[0-9a-f]{32}", response["X-Request-ID"])
    assert not [record for record in logs.records if record.name == "access"]


def test_all_lines_of_a_request_share_its_id(api_client, logs, make_customer):
    make_customer()
    response = log_in(api_client, password="Wrong#123")

    ids = {record.request_id for record in logs.records if record.name in {"audit", "access"}}
    assert ids == {response["X-Request-ID"]}


def test_dev_server_lines_are_silenced_not_left_to_last_resort():
    """runserver's own access lines are replaced by ours, including its 4xx warnings."""
    server = logging.getLogger("django.server")
    assert not server.propagate
    # (pytest adds its own capture handlers during tests; ours is the NullHandler.)
    assert any(type(handler) is logging.NullHandler for handler in server.handlers)


def test_client_errors_are_not_logged_twice(client, logs):
    client.get("/no-such-page")
    assert [record.name for record in logs.records] == ["access"]  # no django.request duplicate


# --- audit events ------------------------------------------------------------------


def test_registration_events(api_client, logs):
    register(api_client)
    register(api_client, email="IOANNIS@example.com")

    succeeded = event(logs, "registration.succeeded")
    assert (succeeded.country, succeeded.ip, succeeded.levelname) == ("GR", "127.0.0.1", "INFO")
    assert isinstance(succeeded.user_id, int)
    assert event(logs, "registration.duplicate_email").email == "io***@example.com"


def test_login_and_logout_events(api_client, logs, make_customer):
    user = make_customer().user

    log_in(api_client, password="Wrong#123")
    log_in(api_client)
    api_client.delete("/api/v1/sessions/current")

    failed = event(logs, "login.failed")
    assert (failed.reason, failed.user_id, failed.levelname) == ("wrong_password", user.pk, "WARNING")
    assert event(logs, "login.succeeded").user_id == user.pk
    assert event(logs, "logout").user_id == user.pk


def test_inactive_account_reason(api_client, logs, make_customer):
    user = make_customer().user
    user.is_active = False
    user.save()

    log_in(api_client)

    assert event(logs, "login.failed").reason == "inactive_account"


def test_rate_limit_event(api_client, logs):
    for _ in range(11):
        log_in(api_client, email="nobody@example.com")

    exceeded = event(logs, "rate_limit.exceeded")
    assert (exceeded.scope, exceeded.ip, exceeded.levelname) == ("login", "127.0.0.1", "WARNING")


def test_csrf_failure_events_on_both_paths(logs, make_customer):
    # Anonymous endpoint: rejected by Django's CSRF middleware.
    APIClient(enforce_csrf_checks=True).post("/api/v1/sessions", {}, format="json")
    # Logged-in endpoint: rejected by DRF's SessionAuthentication.
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(make_customer().user)
    client.delete("/api/v1/sessions/current")

    failures = [record for record in events(logs) if record.event == "csrf.failed"]
    assert [record.path for record in failures] == ["/api/v1/sessions", "/api/v1/sessions/current"]
    assert all(record.reason and record.ip == "127.0.0.1" for record in failures)


# --- no personal data ----------------------------------------------------------------


def test_logs_never_contain_passwords_emails_or_session_ids(api_client, logs):
    register(api_client)
    log_in(api_client, password="Wrong#123")
    log_in(api_client, email="nobody@example.com", password="Other#999")
    log_in(api_client)
    session_id = api_client.cookies["sessionid"].value
    csrf_token = api_client.cookies["csrftoken"].value
    api_client.delete("/api/v1/sessions/current")

    # Exactly what would be shipped: every record, formatted as JSON.
    shipped = "\n".join(JsonFormatter().format(record) for record in logs.records)
    for secret in [PASSWORD, "Wrong#123", "Other#999", "ioannis@example.com",
                   "nobody@example.com", "Papadopoulos", "6912345678", session_id, csrf_token]:
        assert secret not in shipped
    assert all(json.loads(line) for line in shipped.splitlines())
