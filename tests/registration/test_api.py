"""POST /api/v1/registrations, end to end through HTTP."""

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from customers.models import Customer

pytestmark = pytest.mark.django_db

URL = "/api/v1/registrations"
PROBLEM_TYPE = "application/problem+json"

VALID = {
    "first_name": "Ioannis",
    "last_name": "Papadopoulos",
    "country": "GR",
    "phone_code": "30",
    "phone": "6912345678",
    "email": "ioannis@example.com",
    "password": "Secret#123",
    "terms": True,
}


def register(client, **overrides):
    return client.post(URL, {**VALID, **overrides}, format="json")


# --- success ------------------------------------------------------------------------


def test_successful_registration_returns_201_and_the_customer(api_client):
    response = register(api_client)

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "email": "ioannis@example.com",
        "first_name": "Ioannis",
        "last_name": "Papadopoulos",
        "country": "GR",
        "phone": "6912345678",
        "created_at": body["created_at"],
    }


def test_password_is_never_returned(api_client):
    response = register(api_client)
    assert "password" not in response.json()
    assert "Secret#123" not in response.content.decode()


def test_user_and_customer_are_stored(api_client):
    register(api_client, email=" Ioannis@Example.COM ", phone="691 234-5678")

    customer = Customer.objects.select_related("user", "country").get()
    assert customer.user.email == "ioannis@example.com"
    assert customer.country.iso_code == "GR"
    assert customer.phone == "6912345678"
    assert customer.user.password.startswith("argon2$argon2id$")
    assert customer.user.check_password("Secret#123")


def test_password_is_not_trimmed(api_client):
    register(api_client, password=" Secret#123 ")
    assert User.objects.get().check_password(" Secret#123 ")


# --- validation (400) ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("first_name", "Ana", "First name must be longer than 3 characters."),
        ("first_name", "Ιωάννης", "First name must be written in Latin characters, as shown in your passport."),
        ("last_name", "", "Last name is required."),
        ("country", "FR", "Please select a valid country."),
        ("phone_code", "+30", "Country code must be numeric (e.g. 30)."),
        ("phone_code", "44", "Country code does not match the selected country."),
        ("phone", "12ab", "Phone number may only contain digits."),
        ("email", "not-an-email", "Please enter a valid email address (e.g. name@example.com)."),
        ("password", "secret123", "Password must include at least one capital letter and one symbol."),
        ("terms", False, "You must accept the Privacy Policy and Terms and Conditions."),
    ],
)
def test_invalid_field_returns_problem_details(api_client, field, value, message):
    response = register(api_client, **{field: value})

    assert response.status_code == 400
    assert response["Content-Type"] == PROBLEM_TYPE
    assert response.json() == {
        "type": "https://hfmarkets.example/problems/validation-error",
        "title": "Validation failed",
        "status": 400,
        "detail": "One or more fields are invalid.",
        "errors": {field: message},
    }
    assert not User.objects.exists()


def test_all_invalid_fields_reported_at_once(api_client):
    response = api_client.post(URL, {}, format="json")

    assert response.status_code == 400
    assert set(response.json()["errors"]) == {
        "first_name", "last_name", "country", "phone_code", "phone", "email", "password", "terms",
    }


def test_wrong_json_type_is_a_validation_error(api_client):
    response = api_client.post(URL, ["not", "an", "object"], format="json")

    assert response.status_code == 400
    assert "non_field_errors" in response.json()["errors"]


def test_malformed_json_is_rejected(api_client):
    response = api_client.post(URL, "{not json", content_type="application/json")

    assert response.status_code == 400
    assert response["Content-Type"] == PROBLEM_TYPE
    assert response.json()["type"].endswith("/parse-error")


# --- duplicate email (409) ------------------------------------------------------------


def test_duplicate_email_returns_409_case_insensitively(api_client):
    register(api_client)
    response = register(api_client, email="IOANNIS@example.com")

    assert response.status_code == 409
    assert response["Content-Type"] == PROBLEM_TYPE
    assert response.json() == {
        "type": "https://hfmarkets.example/problems/email-already-registered",
        "title": "Email already registered",
        "status": 409,
        "detail": "An account with this email already exists.",
        "errors": {"email": "This email is already registered. Please log in instead."},
    }
    assert User.objects.count() == 1


# --- protocol -------------------------------------------------------------------------


def test_only_json_is_accepted(api_client):
    response = api_client.post(URL, VALID)  # form-encoded

    assert response.status_code == 415
    assert response["Content-Type"] == PROBLEM_TYPE
    assert response.json()["type"].endswith("/unsupported-media-type")


def test_get_is_not_allowed(api_client):
    response = api_client.get(URL)

    assert response.status_code == 405
    assert response["Allow"] == "POST, OPTIONS"
    assert response.json()["type"].endswith("/method-not-allowed")


def test_post_without_csrf_token_is_rejected():
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(URL, VALID, format="json")

    assert response.status_code == 403
    assert not User.objects.exists()


def test_post_with_csrf_token_is_accepted():
    client = APIClient(enforce_csrf_checks=True)
    client.cookies["csrftoken"] = token = "a" * 32
    response = client.post(URL, VALID, format="json", HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 201
