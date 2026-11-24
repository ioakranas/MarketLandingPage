"""Login, lockout, session and login-history tests."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher

from app import services
from app.db import get_db
from app.validation import Registration

EMAIL = "ioannis@example.com"
PASSWORD = "Secret#123"
NOW = datetime(2026, 11, 24, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch):
    """Controllable 'now' for the service layer."""

    class Clock:
        now = NOW

        def advance(self, **delta):
            self.now += timedelta(**delta)

    clock = Clock()
    monkeypatch.setattr(services, "_utcnow", lambda: clock.now)
    return clock


@pytest.fixture
def customer_id(app):
    with app.app_context():
        return services.register_customer(
            Registration("Ioannis", "Papadopoulos", "GR", "6912345678", EMAIL, PASSWORD)
        )


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def attempts(app):
    with app.app_context():
        return get_db().execute(
            "SELECT customer_id, success, ip_address, attempted_at FROM login_attempts ORDER BY id"
        ).fetchall()


# --- page & validation --------------------------------------------------------------


def test_login_page_renders(client):
    html = client.get("/login").get_data(as_text=True)
    assert '<form method="post" action="/login"' in html
    assert 'href="/register"' in html


@pytest.mark.parametrize(
    ("form", "message"),
    [
        ({"email": "", "password": "x"}, "Email is required."),
        ({"email": "not-an-email", "password": "x"}, "Please enter a valid email address"),
        ({"email": EMAIL, "password": ""}, "Password is required."),
    ],
)
def test_invalid_input_shows_specific_message(client, form, message):
    response = client.post("/login", data=form)
    assert response.status_code == 400
    assert message in response.get_data(as_text=True)


# --- success ------------------------------------------------------------------------


def test_successful_login_redirects_to_welcome(client, customer_id):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/welcome"

    html = client.get("/welcome").get_data(as_text=True)
    assert "Welcome back, Ioannis!" in html
    assert "This is your first login." in html


def test_email_is_case_insensitive(client, customer_id):
    assert login(client, email="  IOANNIS@Example.com ").status_code == 302


def test_successful_login_is_recorded(app, client, customer_id, clock):
    login(client)
    [attempt] = attempts(app)
    assert attempt["customer_id"] == customer_id
    assert attempt["success"] == 1
    assert attempt["ip_address"] == "127.0.0.1"
    assert attempt["attempted_at"] == "2026-11-24 12:00:00"


def test_welcome_shows_login_count_and_previous_login(client, customer_id, clock):
    login(client)
    clock.advance(days=1)
    login(client)

    html = client.get("/welcome").get_data(as_text=True)
    assert "This is login #2." in html
    assert "Your previous login was on 2026-11-24 12:00:00 UTC." in html


def test_login_starts_a_fresh_session(client, customer_id):
    with client.session_transaction() as session:
        session["planted"] = "by-attacker"

    login(client)

    with client.session_transaction() as session:
        assert "planted" not in session
        assert session["customer_id"] == customer_id


# --- failures -----------------------------------------------------------------------

GENERIC_ERROR = "Invalid email or password."


def test_wrong_password_is_rejected_and_recorded(app, client, customer_id):
    response = login(client, password="Wrong#123")

    assert response.status_code == 401
    assert GENERIC_ERROR in response.get_data(as_text=True)
    [attempt] = attempts(app)
    assert attempt["success"] == 0


def test_unknown_email_gets_same_message_and_is_not_stored(app, client, customer_id):
    response = login(client, email="nobody@example.com")

    assert response.status_code == 401
    assert GENERIC_ERROR in response.get_data(as_text=True)
    assert attempts(app) == []


def test_unknown_email_is_logged_masked(client, caplog):
    with caplog.at_level(logging.WARNING):
        login(client, email="nobody@example.com")

    assert "Failed login for unknown email no***@example.com from 127.0.0.1" in caplog.text
    assert "nobody@example.com" not in caplog.text


def test_unknown_email_still_runs_password_check(client, monkeypatch):
    """Timing-attack mitigation: unknown emails cost one Argon2 verification too."""
    verified = []
    real_verify = services._verify_quietly
    monkeypatch.setattr(
        services, "_verify_quietly", lambda h, p: verified.append(h) or real_verify(h, p)
    )

    login(client, email="nobody@example.com")

    assert verified == [services._DUMMY_HASH]


def test_form_keeps_email_but_not_password(client, customer_id):
    html = login(client, password="Wrong#123").get_data(as_text=True)
    assert f'value="{EMAIL}"' in html
    assert "Wrong#123" not in html


# --- lockout ------------------------------------------------------------------------

LOCKED = "Too many failed login attempts."


def fail(client, times):
    for _ in range(times):
        login(client, password="Wrong#123")


def test_account_locks_after_five_failures(app, client, customer_id, clock):
    fail(client, 5)

    response = login(client)  # correct password, but locked
    assert response.status_code == 429
    assert "Please try again in 15 minute(s)." in response.get_data(as_text=True)
    # The locked attempt was not evaluated or recorded.
    assert [a["success"] for a in attempts(app)] == [0] * 5


def test_four_failures_do_not_lock(client, customer_id, clock):
    fail(client, 4)
    assert login(client).status_code == 302


def test_lock_reports_remaining_minutes(client, customer_id, clock):
    fail(client, 5)
    clock.advance(minutes=10, seconds=30)

    html = login(client).get_data(as_text=True)
    assert "Please try again in 5 minute(s)." in html


def test_lock_expires_after_window(client, customer_id, clock):
    fail(client, 5)
    clock.advance(minutes=15)

    assert login(client).status_code == 302


def test_last_minute_rounds_up_to_one(client, customer_id, clock):
    fail(client, 5)
    clock.advance(minutes=14, seconds=59)

    assert "Please try again in 1 minute(s)." in login(client).get_data(as_text=True)


def test_failures_spread_beyond_window_do_not_lock(client, customer_id, clock):
    for _ in range(5):
        fail(client, 1)
        clock.advance(minutes=4)  # oldest failure leaves the 15-minute window

    assert login(client).status_code == 302


def test_successful_login_resets_failure_count(client, customer_id, clock):
    fail(client, 4)
    login(client)
    fail(client, 4)

    assert login(client).status_code == 302


def test_lockout_is_per_account(client, customer_id, app, clock):
    with app.app_context():
        services.register_customer(
            Registration("Maria", "Georgiou", "CY", "99123456", "maria@example.com", PASSWORD)
        )
    fail(client, 5)

    assert login(client, email="maria@example.com").status_code == 302


def test_locked_attempt_is_logged(client, customer_id, clock, caplog):
    fail(client, 5)
    with caplog.at_level(logging.WARNING):
        login(client)
    assert f"Login attempt on locked account {customer_id} from 127.0.0.1" in caplog.text


# --- password rehash ----------------------------------------------------------------


def test_outdated_hash_is_upgraded_on_login(app, client, customer_id):
    weak_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE customers SET password_hash = ? WHERE id = ?", (weak_hash, customer_id))
        db.commit()

    assert login(client).status_code == 302

    with app.app_context():
        new_hash = get_db().execute(
            "SELECT password_hash FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()[0]
    assert new_hash != weak_hash
    assert not services.password_hasher.check_needs_rehash(new_hash)
    assert services.password_hasher.verify(new_hash, PASSWORD)


# --- welcome & logout ---------------------------------------------------------------


def test_welcome_requires_login(client):
    response = client.get("/welcome")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_welcome_with_deleted_customer_clears_session(app, client, customer_id):
    login(client)
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        db.commit()

    assert client.get("/welcome").headers["Location"] == "/login"
    with client.session_transaction() as session:
        assert "customer_id" not in session


def test_logout_clears_session(client, customer_id):
    login(client)
    response = client.post("/logout")

    assert response.headers["Location"] == "/login"
    assert client.get("/welcome").headers["Location"] == "/login"


def test_logout_requires_post(client):
    assert client.get("/logout").status_code == 405


# --- retention ----------------------------------------------------------------------


def test_purge_removes_only_old_failed_attempts(app, client, customer_id, clock):
    fail(client, 1)  # old failure: purged
    login(client)  # old success: kept
    clock.advance(days=31)
    fail(client, 1)  # recent failure: kept

    result = app.test_cli_runner().invoke(args=["purge-login-attempts", "--days", "30"])

    assert "Deleted 1 failed login attempt(s) older than 30 day(s)." in result.output
    assert [a["success"] for a in attempts(app)] == [1, 0]


def test_purge_rejects_non_positive_days(app):
    result = app.test_cli_runner().invoke(args=["purge-login-attempts", "--days", "0"])
    assert result.exit_code != 0


# --- helpers ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "masked"),
    [("ioannis@example.com", "io***@example.com"), ("a@example.com", "a***@example.com")],
)
def test_mask_email(email, masked):
    assert services.mask_email(email) == masked
