"""The session API end to end through HTTP: log in, current session, log out."""

from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import LoginAttempt
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

SESSIONS = "/api/v1/sessions"
CURRENT = "/api/v1/sessions/current"
PROBLEM_TYPE = "application/problem+json"
EMAIL = "ioannis@example.com"


def log_in(client, email=EMAIL, password=PASSWORD):
    return client.post(SESSIONS, {"email": email, "password": password}, format="json")


# --- log in -------------------------------------------------------------------------


def test_successful_login_returns_201_and_the_session(api_client, customer, clock):
    response = log_in(api_client)

    assert response.status_code == 201
    assert response["Location"] == CURRENT
    assert response.json() == {
        "email": EMAIL,
        "first_name": "Ioannis",
        "last_name": "Papadopoulos",
        "previous_login_at": None,
    }
    assert "password" not in response.content.decode()


def test_login_history_in_the_response(api_client, customer, clock):
    log_in(api_client)
    clock.advance(days=1)

    body = log_in(api_client).json()
    assert body["previous_login_at"] == "2026-11-24T12:00:00Z"


def test_login_starts_a_new_session(api_client, customer):
    """Session fixation protection: a session id known before login is useless after it."""
    anonymous_session = api_client.session
    anonymous_session.save()
    before = anonymous_session.session_key

    log_in(api_client)

    after = api_client.cookies["sessionid"].value
    assert after != before
    assert not Session.objects.filter(session_key=before).exists()


def test_client_ip_is_recorded(api_client, customer):
    log_in(api_client)
    assert LoginAttempt.objects.get().ip_address == "127.0.0.1"


@pytest.mark.parametrize(
    ("payload", "errors"),
    [
        ({}, {"email": "Email is required.", "password": "Password is required."}),
        (
            {"email": "not-an-email", "password": "x"},
            {"email": "Please enter a valid email address (e.g. name@example.com)."},
        ),
        ({"email": EMAIL, "password": ""}, {"password": "Password is required."}),
    ],
)
def test_invalid_input_is_400_with_field_errors(api_client, payload, errors):
    response = api_client.post(SESSIONS, payload, format="json")

    assert response.status_code == 400
    assert response["Content-Type"] == PROBLEM_TYPE
    assert response.json()["errors"] == errors


def test_wrong_password_and_unknown_email_get_the_identical_401(api_client, customer):
    wrong_password = log_in(api_client, password="Wrong#123")
    unknown_email = log_in(api_client, email="nobody@example.com")

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response["Content-Type"] == PROBLEM_TYPE
        assert response["WWW-Authenticate"] == 'Session realm="api"'
    assert wrong_password.json() == unknown_email.json() == {
        "type": "https://hfmarkets.example/problems/invalid-credentials",
        "title": "Invalid credentials",
        "status": 401,
        "detail": "Invalid email or password.",
    }


def test_failed_login_does_not_create_a_session(api_client, customer):
    log_in(api_client, password="Wrong#123")
    assert api_client.get(CURRENT).status_code == 401


def test_locked_account_is_429_with_retry_after(api_client, customer, clock):
    for _ in range(5):
        log_in(api_client, password="Wrong#123")

    response = log_in(api_client)  # right password, but locked

    assert response.status_code == 429
    assert response["Retry-After"] == "900"
    assert response.json() == {
        "type": "https://hfmarkets.example/problems/account-locked",
        "title": "Account temporarily locked",
        "status": 429,
        "detail": "Too many failed login attempts. Please try again in 15 minute(s).",
    }
    assert api_client.get(CURRENT).status_code == 401


def test_login_requires_csrf_token():
    response = log_in(APIClient(enforce_csrf_checks=True))

    assert response.status_code == 403
    assert response.json()["type"].endswith("/csrf-failed")


def test_login_with_csrf_token(customer):
    client = APIClient(enforce_csrf_checks=True)
    client.cookies["csrftoken"] = token = "a" * 32

    response = client.post(
        SESSIONS, {"email": EMAIL, "password": PASSWORD}, format="json", HTTP_X_CSRFTOKEN=token
    )

    assert response.status_code == 201
    assert client.cookies["csrftoken"].value != token  # rotated on login


# --- current session ----------------------------------------------------------------


def test_current_session_after_login(api_client, customer):
    log_in(api_client)

    response = api_client.get(CURRENT)

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL
    assert response.json()["previous_login_at"] is None


def test_current_session_without_login_is_401_problem(api_client):
    response = api_client.get(CURRENT)

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == 'Session realm="api"'
    assert response.json() == {
        "type": "https://hfmarkets.example/problems/not-authenticated",
        "title": "Unauthorized",
        "status": 401,
        "detail": "Authentication credentials were not provided.",
    }


def test_deactivated_account_loses_its_session(api_client, customer):
    log_in(api_client)
    customer.user.is_active = False
    customer.user.save()

    assert api_client.get(CURRENT).status_code == 401


# --- idle timeout -------------------------------------------------------------------


def stored_session(client) -> Session:
    return Session.objects.get(session_key=client.cookies["sessionid"].value)


def test_session_expires_after_30_idle_minutes(api_client, customer):
    log_in(api_client)
    session = stored_session(api_client)
    session.expire_date = timezone.now() - timedelta(seconds=1)  # 30 idle minutes passed
    session.save()

    assert api_client.get(CURRENT).status_code == 401


def test_activity_pushes_the_expiry_forward(api_client, customer):
    log_in(api_client)
    session = stored_session(api_client)
    session.expire_date = timezone.now() + timedelta(minutes=1)  # about to expire
    session.save()

    assert api_client.get(CURRENT).status_code == 200

    remaining = stored_session(api_client).expire_date - timezone.now()
    assert timedelta(minutes=29) < remaining <= timedelta(minutes=30)


# --- log out ------------------------------------------------------------------------


def test_logout_deletes_the_server_side_session(api_client, customer):
    log_in(api_client)
    session_key = api_client.cookies["sessionid"].value

    response = api_client.delete(CURRENT)

    assert response.status_code == 204
    assert not Session.objects.filter(session_key=session_key).exists()
    assert api_client.get(CURRENT).status_code == 401


def test_stolen_session_cookie_stops_working_after_logout(api_client, customer):
    log_in(api_client)
    thief = APIClient()
    thief.cookies["sessionid"] = api_client.cookies["sessionid"].value
    assert thief.get(CURRENT).status_code == 200

    api_client.delete(CURRENT)

    assert thief.get(CURRENT).status_code == 401


def test_logout_without_session_is_401(api_client):
    assert api_client.delete(CURRENT).status_code == 401


def test_logout_requires_csrf_token(customer):
    """Logged-in requests are CSRF-checked by DRF: another site can't log users out."""
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(customer.user)

    response = client.delete(CURRENT)

    assert response.status_code == 403
    assert response["Content-Type"] == PROBLEM_TYPE
    assert response.json() == {
        "type": "https://hfmarkets.example/problems/csrf-failed",
        "title": "Forbidden",
        "status": 403,
        "detail": "CSRF verification failed. Reload the page and try again.",
    }


def test_sessions_collection_only_accepts_post(api_client):
    response = api_client.get(SESSIONS)
    assert response.status_code == 405
    assert response["Allow"] == "POST, OPTIONS"
