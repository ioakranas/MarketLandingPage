"""The admin login goes through the same login service: lockout, records, audit."""

import logging

import pytest

from accounts.models import User
from authentication.models import LoginAttempt

pytestmark = pytest.mark.django_db

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin#12345"


@pytest.fixture
def staff(db):
    return User.objects.create_superuser(ADMIN_EMAIL, ADMIN_PASSWORD)


def admin_login(client, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    return client.post(
        "/admin/login/?next=/admin/", {"username": email, "password": password}
    )


def test_staff_can_log_in_and_the_login_is_recorded(client, staff, caplog):
    with caplog.at_level(logging.INFO):
        response = admin_login(client, email="ADMIN@example.com")

    assert response.status_code == 302
    assert response["Location"] == "/admin/"
    assert LoginAttempt.objects.get().succeeded is True
    assert any(getattr(record, "event", None) == "login.succeeded" for record in caplog.records)


def test_wrong_password_is_recorded_and_shows_the_admin_message(client, staff):
    response = admin_login(client, password="Wrong#123")

    assert response.status_code == 200
    assert "correct email and password for a staff account" in (
        response.content.decode()
    )
    assert LoginAttempt.objects.get().succeeded is False


def test_admin_login_is_locked_after_five_failures(client, staff):
    for _ in range(5):
        admin_login(client, password="Wrong#123")

    response = admin_login(client)  # right password, but locked

    assert response.status_code == 200
    assert "Too many failed login attempts. Please try again in 15 minute(s)." in (
        response.content.decode()
    )
    assert client.get("/admin/").status_code == 302  # not logged in


def test_customers_cannot_use_the_admin(client, make_customer):
    make_customer()
    response = admin_login(client, email="ioannis@example.com", password="Secret#123")

    assert response.status_code == 200
    assert "for a staff account" in response.content.decode()
    assert client.get("/admin/").status_code == 302


def test_empty_fields_are_form_errors_not_attempts(client, staff):
    response = admin_login(client, password="")

    assert response.status_code == 200
    assert "This field is required." in response.content.decode()
    assert not LoginAttempt.objects.exists()
