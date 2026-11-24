"""End-to-end tests of the registration flow through the HTTP test client."""

import re

import pytest
from argon2 import PasswordHasher

from app import create_app
from app.db import get_db
from app.services import register_customer
from app.validation import Registration

VALID_FORM = {
    "first_name": "Ioannis",
    "last_name": "Papadopoulos",
    "country": "GR",
    "phone_code": "30",
    "phone": "6912345678",
    "email": "ioannis@example.com",
    "password": "Secret#123",
    "terms": "on",
}


def submit(client, **overrides):
    return client.post("/register", data={**VALID_FORM, **overrides})


def fetch_customers(app):
    with app.app_context():
        return get_db().execute(
            """
            SELECT c.*, co.iso_code FROM customers c
            JOIN countries co ON co.id = c.country_id
            """
        ).fetchall()


# --- pages --------------------------------------------------------------------------


def test_root_redirects_to_register(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/register"


def test_register_page_lists_countries_from_database(client):
    html = client.get("/register").get_data(as_text=True)
    assert 'value="GR" data-dial-code="30"' in html
    assert 'value="CY" data-dial-code="357"' in html
    assert 'value="GB" data-dial-code="44"' in html


# --- successful sign-up -------------------------------------------------------------


def test_successful_registration_redirects_to_thank_you(client):
    response = submit(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/register/success"

    page = client.get("/register/success").get_data(as_text=True)
    assert "Thank you for signing up, Ioannis!" in page


def test_customer_is_stored_with_normalised_data(app, client):
    submit(client, email=" Ioannis@Example.COM ", phone="691 234 5678")

    [customer] = fetch_customers(app)
    assert customer["first_name"] == "Ioannis"
    assert customer["iso_code"] == "GR"
    assert customer["phone"] == "6912345678"
    assert customer["email"] == "ioannis@example.com"


def test_password_is_stored_as_argon2id_hash(app, client):
    submit(client)

    [customer] = fetch_customers(app)
    assert customer["password_hash"].startswith("$argon2id$")
    assert "Secret#123" not in customer["password_hash"]
    assert PasswordHasher().verify(customer["password_hash"], "Secret#123")


def test_same_password_gets_different_hashes(app, client):
    submit(client, email="first@example.com")
    submit(client, email="second@example.com")

    first, second = fetch_customers(app)
    assert first["password_hash"] != second["password_hash"]  # random salt per hash


def test_thank_you_page_is_shown_only_once(client):
    submit(client)
    client.get("/register/success")

    response = client.get("/register/success")
    assert response.status_code == 302
    assert response.headers["Location"] == "/register"


def test_thank_you_page_without_registration_redirects(client):
    response = client.get("/register/success")
    assert response.status_code == 302
    assert response.headers["Location"] == "/register"


# --- validation failures ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("first_name", "Ana", "First name must be longer than 3 characters."),
        ("last_name", "Li", "Last name must be longer than 3 characters."),
        ("country", "FR", "Please select a valid country."),
        ("phone_code", "+30", "Country code must be numeric (e.g. 30)."),
        ("phone_code", "44", "Country code does not match the selected country."),
        ("phone", "12ab", "Phone number may only contain digits."),
        ("email", "not-an-email", "Please enter a valid email address (e.g. name@example.com)."),
        ("password", "secret123", "Password must include at least one capital letter and one symbol."),
        ("terms", "", "You must accept the Privacy Policy and Terms and Conditions."),
    ],
)
def test_invalid_field_shows_specific_message(app, client, field, value, message):
    response = submit(client, **{field: value})

    assert response.status_code == 400
    assert message in response.get_data(as_text=True)
    assert fetch_customers(app) == []


def test_form_keeps_entered_values_but_never_the_password(client):
    html = submit(client, first_name="Ana").get_data(as_text=True)

    assert 'value="Ana"' in html
    assert 'value="ioannis@example.com"' in html
    assert re.search(r'<option value="GR" data-dial-code="30"\s+selected>', html)
    assert "Secret#123" not in html


def test_submitted_values_are_html_escaped(client):
    html = submit(client, first_name='"><script>alert(1)</script>').get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html
    assert "&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_sql_injection_attempt_is_stored_as_plain_text(app, client):
    # Passes validation (valid email syntax) and must be stored verbatim, not executed.
    response = submit(client, email="x'or'1'='1@example.com")

    assert response.status_code == 302
    [customer] = fetch_customers(app)
    assert customer["email"] == "x'or'1'='1@example.com"


# --- duplicate email ----------------------------------------------------------------


def test_duplicate_email_is_rejected_case_insensitively(app, client):
    submit(client)
    response = submit(client, email="IOANNIS@example.com")

    assert response.status_code == 409
    assert "This email is already registered." in response.get_data(as_text=True)
    assert len(fetch_customers(app)) == 1


def test_other_integrity_errors_are_not_mistaken_for_duplicates(app):
    registration = Registration("Ioannis", "Papadopoulos", "XX", "6912345678", "a@b.co", "Secret#123")
    with app.app_context(), pytest.raises(Exception, match="NOT NULL constraint failed"):
        register_customer(registration)


# --- CSRF ---------------------------------------------------------------------------


@pytest.fixture
def csrf_client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(tmp_path / "csrf.sqlite3"),
            "WTF_CSRF_ENABLED": True,
        }
    )
    return app.test_client()


def test_post_without_csrf_token_is_rejected(csrf_client):
    response = csrf_client.post("/register", data=VALID_FORM)

    assert response.status_code == 400
    assert "Your session has expired" in response.get_data(as_text=True)


def test_post_with_valid_csrf_token_is_accepted(csrf_client):
    html = csrf_client.get("/register").get_data(as_text=True)
    token = html.split('name="csrf_token" value="')[1].split('"')[0]

    response = csrf_client.post("/register", data={**VALID_FORM, "csrf_token": token})
    assert response.status_code == 302
