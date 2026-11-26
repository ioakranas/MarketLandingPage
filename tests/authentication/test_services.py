"""Login rules: credentials, lockout, attempt records, rehash, retention."""

import logging
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password

from authentication.models import LoginAttempt
from authentication.selectors import session_summary
from authentication.services import (
    AccountLocked,
    InvalidCredentials,
    authenticate_customer,
    purge_failed_login_attempts,
)
from common.validation import LoginCredentials
from tests.authentication.conftest import NOW
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

EMAIL = "ioannis@example.com"
IP = "203.0.113.7"


def log_in(email=EMAIL, password=PASSWORD, ip=IP):
    return authenticate_customer(LoginCredentials(email, password), ip_address=ip)


def fail(times):
    for _ in range(times):
        with pytest.raises(InvalidCredentials):
            log_in(password="Wrong#123")


def outcomes():
    return list(LoginAttempt.objects.order_by("id").values_list("succeeded", flat=True))


# --- credentials --------------------------------------------------------------------


def test_valid_credentials_return_the_user_and_record_success(customer, clock):
    assert log_in() == customer.user

    [attempt] = LoginAttempt.objects.all()
    assert (attempt.user, attempt.succeeded, attempt.ip_address) == (customer.user, True, IP)
    assert attempt.attempted_at == NOW


def test_email_lookup_is_case_insensitive(customer):
    assert log_in(email="IOANNIS@Example.com") == customer.user


def test_wrong_password_is_recorded_as_failure(customer):
    fail(1)
    assert outcomes() == [False]


def test_unknown_email_is_not_stored_but_logged_masked(customer, caplog):
    with caplog.at_level(logging.WARNING), pytest.raises(InvalidCredentials):
        log_in(email="nobody@example.com")

    assert not LoginAttempt.objects.exists()
    [record] = [r for r in caplog.records if r.name == "audit"]
    assert (record.event, record.reason, record.email, record.ip) == (
        "login.failed",
        "unknown_email",
        "no***@example.com",
        IP,
    )
    assert "nobody@example.com" not in caplog.text


def test_unknown_email_still_costs_one_password_hash(db, monkeypatch):
    """Timing-attack mitigation (Django's): no account takes as long as a wrong password."""
    from django.contrib.auth import base_user

    hashed = []
    real = base_user.make_password
    monkeypatch.setattr(base_user, "make_password", lambda p, *a: hashed.append(p) or real(p, *a))

    with pytest.raises(InvalidCredentials):
        log_in(email="nobody@example.com")

    assert hashed == [PASSWORD]


def test_inactive_account_cannot_log_in_even_with_the_right_password(customer):
    customer.user.is_active = False
    customer.user.save()

    with pytest.raises(InvalidCredentials):
        log_in()
    assert outcomes() == [False]


def test_outdated_hash_is_upgraded_on_successful_login(customer, settings):
    """Django rehashes with the preferred hasher when the password is known to be right."""
    settings.PASSWORD_HASHERS = [
        "tests.hashers.FastArgon2PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]
    user = customer.user
    user.password = make_password(PASSWORD, hasher="pbkdf2_sha256")
    user.save()

    log_in()

    user.refresh_from_db()
    assert user.password.startswith("argon2$")
    assert user.check_password(PASSWORD)


# --- lockout ------------------------------------------------------------------------


def test_five_failures_lock_the_account_even_for_the_right_password(customer, clock):
    fail(5)

    with pytest.raises(AccountLocked) as locked:
        log_in()

    assert locked.value.retry_after == timedelta(minutes=15)
    assert locked.value.minutes_remaining == 15
    assert outcomes() == [False] * 5  # the locked attempt was not evaluated or recorded


def test_four_failures_do_not_lock(customer, clock):
    fail(4)
    assert log_in() == customer.user


def test_lock_reports_remaining_time(customer, clock):
    fail(5)
    clock.advance(minutes=10, seconds=30)

    with pytest.raises(AccountLocked) as locked:
        log_in()
    assert locked.value.retry_after == timedelta(minutes=4, seconds=30)
    assert locked.value.minutes_remaining == 5  # rounded up


def test_last_second_still_reports_one_minute(customer, clock):
    fail(5)
    clock.advance(minutes=14, seconds=59)

    with pytest.raises(AccountLocked) as locked:
        log_in()
    assert locked.value.minutes_remaining == 1


def test_lock_expires_after_the_window(customer, clock):
    fail(5)
    clock.advance(minutes=15)

    assert log_in() == customer.user


def test_failures_spread_beyond_the_window_do_not_lock(customer, clock):
    for _ in range(5):
        fail(1)
        clock.advance(minutes=4)  # the oldest failure leaves the 15-minute window

    assert log_in() == customer.user


def test_successful_login_resets_the_failure_count(customer, clock):
    fail(4)
    log_in()
    fail(4)

    assert log_in() == customer.user


def test_lockout_is_per_account(customer, make_customer, clock):
    other = make_customer(email="maria@example.com")
    fail(5)

    assert log_in(email="maria@example.com") == other.user


def test_locked_attempt_is_logged(customer, clock, caplog):
    fail(5)
    with caplog.at_level(logging.WARNING), pytest.raises(AccountLocked):
        log_in()

    locked = [r for r in caplog.records if getattr(r, "event", None) == "login.locked"]
    assert [(r.user_id, r.ip, r.levelname) for r in locked] == [(customer.user.pk, IP, "WARNING")]


def test_lockout_threshold_and_window_come_from_settings(customer, clock, settings):
    settings.LOGIN_LOCKOUT_THRESHOLD = 2
    settings.LOGIN_LOCKOUT_WINDOW = timedelta(minutes=1)
    fail(2)

    with pytest.raises(AccountLocked) as locked:
        log_in()
    assert locked.value.retry_after == timedelta(minutes=1)


# --- history ------------------------------------------------------------------------


def test_session_summary_shows_the_previous_successful_login(customer, clock):
    log_in()
    clock.advance(days=1)
    fail(1)  # failures are not logins
    log_in()

    summary = session_summary(customer.user)
    assert summary.previous_login_at == NOW
    assert (summary.first_name, summary.last_name) == ("Ioannis", "Papadopoulos")


def test_first_login_has_no_previous_login(customer):
    log_in()
    summary = session_summary(customer.user)
    assert summary.previous_login_at is None


def test_staff_account_without_customer_profile(make_user):
    summary = session_summary(make_user("staff@example.com"))
    assert (summary.email, summary.first_name, summary.last_name) == ("staff@example.com", None, None)


# --- retention ----------------------------------------------------------------------


def test_purge_deletes_only_old_failures(customer, clock):
    log_in()
    fail(1)  # old failure
    clock.advance(days=31)
    fail(1)  # recent failure

    assert purge_failed_login_attempts(timedelta(days=30)) == 1
    assert outcomes() == [True, False]  # the login history and the recent failure stay
