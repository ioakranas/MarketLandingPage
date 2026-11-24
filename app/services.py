"""Business logic (the @Service layer): routes call these, these talk to the database."""

import sqlite3

from argon2 import PasswordHasher

from app.db import get_db
from app.validation import Registration

# Argon2id with the library defaults (RFC 9106 "low memory" profile: 64 MiB, 3 passes,
# 4 lanes). Each hash embeds its own random salt and parameters.
password_hasher = PasswordHasher()


class EmailAlreadyRegistered(Exception):
    pass


def get_countries() -> list[sqlite3.Row]:
    return get_db().execute("SELECT iso_code, name, dial_code FROM countries ORDER BY name").fetchall()


def get_dial_codes() -> dict[str, str]:
    """{"GR": "30", ...}: the allowed countries, as the validator expects them."""
    return {row["iso_code"]: row["dial_code"] for row in get_countries()}


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
