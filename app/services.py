"""Business logic (the @Service layer): routes call these, these talk to the database."""

import math
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app

from app.db import get_db
from app.validation import LoginCredentials, Registration

# Argon2id with the library defaults (RFC 9106 "low memory" profile: 64 MiB, 3 passes,
# 4 lanes). Each hash embeds its own random salt and parameters.
password_hasher = PasswordHasher()

# Verified against when the email is unknown, so that "no such user" takes as long as
# "wrong password" and response times don't reveal which emails are registered.
_DUMMY_HASH = password_hasher.hash("timing-attack-mitigation")

# Same format as SQLite's CURRENT_TIMESTAMP, so stored values compare as text.
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class AccountLocked(Exception):
    def __init__(self, minutes_remaining: int):
        super().__init__(f"Account locked for {minutes_remaining} more minute(s)")
        self.minutes_remaining = minutes_remaining


@dataclass(frozen=True)
class LoginStats:
    login_count: int
    previous_login_at: str | None  # UTC, None on the first login


# --- countries ----------------------------------------------------------------------


def get_countries() -> list[sqlite3.Row]:
    return get_db().execute("SELECT iso_code, name, dial_code FROM countries ORDER BY name").fetchall()


def get_dial_codes() -> dict[str, str]:
    """{"GR": "30", ...}: the allowed countries, as the validator expects them."""
    return {row["iso_code"]: row["dial_code"] for row in get_countries()}


# --- registration -------------------------------------------------------------------


def register_customer(registration: Registration) -> int:
    """Store a new customer and return its id.

    Duplicate emails are detected by the UNIQUE constraint rather than a prior SELECT:
    a check-then-insert would race when two sign-ups for the same email arrive together.
    """
    password_hash = password_hasher.hash(registration.password)
    db = get_db()
    try:
        cursor = db.execute(
            """
            INSERT INTO customers (first_name, last_name, country_id, phone, email, password_hash)
            VALUES (?, ?, (SELECT id FROM countries WHERE iso_code = ?), ?, ?, ?)
            """,
            (
                registration.first_name,
                registration.last_name,
                registration.country_iso,
                registration.phone,
                registration.email,
                password_hash,
            ),
        )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed: customers.email" in str(error):
            raise EmailAlreadyRegistered from error
        raise
    db.commit()
    return cursor.lastrowid


# --- login --------------------------------------------------------------------------


def authenticate(credentials: LoginCredentials, ip_address: str | None) -> sqlite3.Row:
    """Return the customer if the credentials are valid.

    Raises InvalidCredentials (same error for unknown email and wrong password) or
    AccountLocked after too many recent failures.
    """
    db = get_db()
    customer = db.execute(
        "SELECT id, first_name, password_hash FROM customers WHERE email = ?",
        (credentials.email,),
    ).fetchone()

    if customer is None:
        _verify_quietly(_DUMMY_HASH, credentials.password)
        # Not stored in the database (bots could flood it); logged for monitoring with
        # a masked address, since a mistyped email is still personal data.
        current_app.logger.warning(
            "Failed login for unknown email %s from %s", mask_email(credentials.email), ip_address
        )
        raise InvalidCredentials

    # Checked before the password: while locked, guesses are not even evaluated.
    minutes_remaining = _lockout_minutes_remaining(customer["id"])
    if minutes_remaining:
        current_app.logger.warning(
            "Login attempt on locked account %s from %s", customer["id"], ip_address
        )
        raise AccountLocked(minutes_remaining)

    if not _verify_quietly(customer["password_hash"], credentials.password):
        _record_attempt(customer["id"], success=False, ip_address=ip_address)
        raise InvalidCredentials

    if password_hasher.check_needs_rehash(customer["password_hash"]):
        # Hashing parameters were raised since this hash was made: upgrade it now,
        # the only moment we have the plain password.
        db.execute(
            "UPDATE customers SET password_hash = ? WHERE id = ?",
            (password_hasher.hash(credentials.password), customer["id"]),
        )
    _record_attempt(customer["id"], success=True, ip_address=ip_address)
    return customer


def get_customer(customer_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        "SELECT id, first_name, last_name, email FROM customers WHERE id = ?", (customer_id,)
    ).fetchone()


def get_login_stats(customer_id: int) -> LoginStats:
    """Total successful logins and the one before the current session."""
    rows = get_db().execute(
        """
        SELECT attempted_at FROM login_attempts
        WHERE customer_id = ? AND success = 1
        ORDER BY id DESC
        """,
        (customer_id,),
    ).fetchall()
    previous = rows[1]["attempted_at"] if len(rows) > 1 else None
    return LoginStats(login_count=len(rows), previous_login_at=previous)


def purge_failed_login_attempts(older_than_days: int) -> int:
    """Retention: delete failed attempts older than the given age. Returns rows deleted."""
    cutoff = _format(_utcnow() - timedelta(days=older_than_days))
    db = get_db()
    cursor = db.execute(
        "DELETE FROM login_attempts WHERE success = 0 AND attempted_at < ?", (cutoff,)
    )
    db.commit()
    return cursor.rowcount


def mask_email(email: str) -> str:
    """ioannis@example.com -> io***@example.com"""
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}"


# --- internals ----------------------------------------------------------------------


def _verify_quietly(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _lockout_minutes_remaining(customer_id: int) -> int:
    """Minutes until the account unlocks, or 0 if it is not locked.

    Locked = at least LOCKOUT_THRESHOLD failures within LOCKOUT_WINDOW_MINUTES, counting
    only failures after the last successful login (a success resets the counter).
    """
    threshold = current_app.config["LOCKOUT_THRESHOLD"]
    window = timedelta(minutes=current_app.config["LOCKOUT_WINDOW_MINUTES"])
    now = _utcnow()

    recent_failures = get_db().execute(
        """
        SELECT attempted_at FROM login_attempts
        WHERE customer_id = ?1
          AND success = 0
          AND attempted_at > ?2
          AND id > COALESCE(
                (SELECT MAX(id) FROM login_attempts WHERE customer_id = ?1 AND success = 1), 0)
        ORDER BY id DESC
        LIMIT ?3
        """,
        (customer_id, _format(now - window), threshold),
    ).fetchall()

    if len(recent_failures) < threshold:
        return 0
    # The lock lasts until the oldest of the last N failures leaves the window.
    oldest = datetime.strptime(recent_failures[-1]["attempted_at"], _TIMESTAMP_FORMAT)
    unlocks_at = oldest.replace(tzinfo=UTC) + window
    return max(1, math.ceil((unlocks_at - now).total_seconds() / 60))


def _record_attempt(customer_id: int, *, success: bool, ip_address: str | None) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO login_attempts (customer_id, success, ip_address, attempted_at)
        VALUES (?, ?, ?, ?)
        """,
        (customer_id, int(success), ip_address, _format(_utcnow())),
    )
    db.commit()


def _utcnow() -> datetime:
    """Single clock for the service, replaceable in tests."""
    return datetime.now(UTC)


def _format(moment: datetime) -> str:
    return moment.strftime(_TIMESTAMP_FORMAT)
