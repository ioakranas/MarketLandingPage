"""Schema-level tests: these prove the database itself rejects invalid data,
independently of the Python validation layer."""

import sqlite3

import pytest

from app.db import close_db, get_db, init_db

VALID_CUSTOMER = {
    "first_name": "Ioannis",
    "last_name": "Papadopoulos",
    "country_id": 1,
    "phone": "6912345678",
    "email": "ioannis@example.com",
    "password_hash": "$argon2id$placeholder",
}


def insert_customer(db, **overrides):
    row = {**VALID_CUSTOMER, **overrides}
    cursor = db.execute(
        """
        INSERT INTO customers (first_name, last_name, country_id, phone, email, password_hash)
        VALUES (:first_name, :last_name, :country_id, :phone, :email, :password_hash)
        """,
        row,
    )
    return cursor.lastrowid


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


# --- initialisation -----------------------------------------------------------------


def test_countries_are_seeded(db):
    rows = db.execute("SELECT iso_code, name, dial_code FROM countries ORDER BY id").fetchall()
    assert [tuple(row) for row in rows] == [
        ("GR", "Greece", "30"),
        ("CY", "Cyprus", "357"),
        ("GB", "United Kingdom", "44"),
    ]


def test_init_db_is_idempotent(app, db):
    insert_customer(db)
    db.commit()

    init_db()
    init_db()

    assert db.execute("SELECT COUNT(*) FROM countries").fetchone()[0] == 3
    assert db.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1


def test_init_db_cli_command(app):
    result = app.test_cli_runner().invoke(args=["init-db"])
    assert "Database initialised." in result.output


# --- connection lifecycle -----------------------------------------------------------


def test_same_connection_within_one_context(app):
    with app.app_context():
        assert get_db() is get_db()


def test_connection_closed_when_context_ends(app):
    with app.app_context():
        connection = get_db()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_close_db_without_open_connection_is_noop(app):
    with app.app_context():
        close_db()


def test_foreign_keys_enabled(db):
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# --- customers constraints ----------------------------------------------------------


def test_valid_customer_is_stored_with_timestamp(db):
    customer_id = insert_customer(db)
    row = db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    assert row["email"] == "ioannis@example.com"
    assert row["created_at"]


@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize("value", ["", "Ana", "x" * 51])
def test_name_length_rejected(db, field, value):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_customer(db, **{field: value})


@pytest.mark.parametrize("value", ["Nick", "Ιωάννης", "x" * 50])
def test_name_length_boundaries_accepted(db, value):
    insert_customer(db, first_name=value, last_name=value)


def test_unknown_country_rejected_by_foreign_key(db):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        insert_customer(db, country_id=999)


@pytest.mark.parametrize("phone", ["12345", "123456789012345", "69123abc78", "+306912345"])
def test_invalid_phone_rejected(db, phone):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_customer(db, phone=phone)


def test_email_unique_case_insensitive(db):
    insert_customer(db, email="ioannis@example.com")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert_customer(db, email="IOANNIS@Example.com")


@pytest.mark.parametrize("email", ["not-an-email", "@example.com", "a" * 250 + "@x.gr"])
def test_malformed_email_rejected(db, email):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_customer(db, email=email)


def test_strict_table_rejects_wrong_type(db):
    with pytest.raises(sqlite3.IntegrityError, match="cannot store TEXT value in INTEGER column"):
        insert_customer(db, country_id="Greece")


@pytest.mark.parametrize("missing", ["first_name", "email", "password_hash"])
def test_required_columns(db, missing):
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        insert_customer(db, **{missing: None})


# --- login_attempts constraints -----------------------------------------------------


def test_login_attempt_requires_existing_customer(db):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute("INSERT INTO login_attempts (customer_id, success) VALUES (999, 1)")


def test_login_attempt_success_must_be_boolean(db):
    customer_id = insert_customer(db)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute(
            "INSERT INTO login_attempts (customer_id, success) VALUES (?, 2)", (customer_id,)
        )


def test_login_attempts_deleted_with_customer(db):
    customer_id = insert_customer(db)
    db.execute("INSERT INTO login_attempts (customer_id, success) VALUES (?, 1)", (customer_id,))
    db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    assert db.execute("SELECT COUNT(*) FROM login_attempts").fetchone()[0] == 0


def test_lockout_query_uses_index(db):
    plan = db.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT COUNT(*) FROM login_attempts
        WHERE customer_id = ? AND success = 0 AND attempted_at >= ?
        """,
        (1, "2026-01-01 00:00:00"),
    ).fetchall()
    assert any("idx_login_attempts_customer_time" in row["detail"] for row in plan)
