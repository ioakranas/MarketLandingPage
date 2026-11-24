"""Unit tests for app.validation: pure functions, no app or database needed."""

import pytest

from app.validation import (
    LoginCredentials,
    Registration,
    validate_login,
    validate_registration,
)

DIAL_CODES = {"GR": "30", "CY": "357", "GB": "44"}

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


def register(**overrides):
    return validate_registration({**VALID_FORM, **overrides}, DIAL_CODES)


def error_for(field, **overrides):
    data, errors = register(**overrides)
    assert data is None
    return errors.get(field)


# --- happy path ---------------------------------------------------------------------


def test_valid_registration_returns_clean_data():
    data, errors = register()
    assert errors == {}
    assert data == Registration(
        first_name="Ioannis",
        last_name="Papadopoulos",
        country_iso="GR",
        phone="6912345678",
        email="ioannis@example.com",
        password="Secret#123",
    )


def test_input_is_normalised():
    data, _ = register(
        first_name="  Ioannis ",
        country=" gr ",
        phone_code=" 30 ",
        phone="691 234-5678",
        email="  Ioannis@Example.COM ",
    )
    assert data.first_name == "Ioannis"
    assert data.country_iso == "GR"
    assert data.phone == "6912345678"
    assert data.email == "ioannis@example.com"


def test_password_is_not_trimmed():
    data, _ = register(password=" Secret#123 ")
    assert data.password == " Secret#123 "


def test_every_invalid_field_is_reported_at_once():
    _, errors = validate_registration({}, DIAL_CODES)
    assert set(errors) == {
        "first_name",
        "last_name",
        "country",
        "phone_code",
        "phone",
        "email",
        "password",
        "terms",
    }


LATIN_ONLY = "First name must be written in Latin characters, as shown in your passport."


# --- names --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "First name is required."),
        ("   ", "First name is required."),
        ("Ana", "First name must be longer than 3 characters."),
        (" Ana ", "First name must be longer than 3 characters."),
        ("x" * 51, "First name must be at most 50 characters."),
        ("John3", "First name may only contain letters, spaces, hyphens and apostrophes."),
        ("<script>", "First name may only contain letters, spaces, hyphens and apostrophes."),
        ("Robert'); DROP TABLE customers;--", "First name may only contain letters, spaces, hyphens and apostrophes."),
        ("-Anna", "First name must start and end with a letter."),
        ("Anna'", "First name must start and end with a letter."),
        ("Ιωάννης", LATIN_ONLY),
        ("Иван", LATIN_ONLY),
        ("Ioаnnis", LATIN_ONLY),  # Cyrillic "а" disguised as Latin "a"
        ("李小龙先生", LATIN_ONLY),
    ],
)
def test_invalid_first_name(value, message):
    assert error_for("first_name", first_name=value) == message


def test_last_name_uses_its_own_label():
    assert error_for("last_name", last_name="Li") == "Last name must be longer than 3 characters."


@pytest.mark.parametrize(
    "value",
    ["Nick", "Anne-Marie", "O'Brien", "Mary Jane", "Chloë", "José", "Müller", "Çelik", "Strauß", "x" * 50],
)
def test_valid_names(value):
    data, errors = register(first_name=value, last_name=value)
    assert errors == {}
    assert data.first_name == value


def test_decomposed_unicode_is_normalised():
    # "Zoë" typed as "Zoe" + combining diaeresis: 4 code points, 3 characters.
    data, errors = register(first_name="Zoëy")
    assert errors == {}
    assert data.first_name == "Zoëy"


# --- country & dial code ------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "Please select a country."),
        ("FR", "Please select a valid country."),
        ("Greece", "Please select a valid country."),
    ],
)
def test_invalid_country(value, message):
    assert error_for("country", country=value) == message


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "Country code is required."),
        ("abc", "Country code must be numeric (e.g. 30)."),
        ("+30", "Country code must be numeric (e.g. 30)."),
        ("3a", "Country code must be numeric (e.g. 30)."),
        ("12345", "Country code must be numeric (e.g. 30)."),
        ("44", "Country code does not match the selected country."),
    ],
)
def test_invalid_phone_code(value, message):
    assert error_for("phone_code", phone_code=value) == message


@pytest.mark.parametrize(("country", "code"), [("GR", "30"), ("CY", "357"), ("GB", "44")])
def test_matching_phone_codes(country, code):
    _, errors = register(country=country, phone_code=code)
    assert errors == {}


def test_phone_code_format_still_checked_without_valid_country():
    _, errors = register(country="", phone_code="abc")
    assert errors["phone_code"] == "Country code must be numeric (e.g. 30)."


def test_phone_code_not_matched_without_valid_country():
    _, errors = register(country="FR", phone_code="33")
    assert "phone_code" not in errors


# --- phone --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "Phone number is required."),
        (" - ", "Phone number is required."),
        ("69123abc", "Phone number may only contain digits."),
        ("+306912345678", "Phone number may only contain digits."),
        ("12345", "Phone number must be between 6 and 14 digits."),
        ("1" * 15, "Phone number must be between 6 and 14 digits."),
        ("６９１２３４５６７８", "Phone number may only contain digits."),  # full-width digits
    ],
)
def test_invalid_phone(value, message):
    assert error_for("phone", phone=value) == message


@pytest.mark.parametrize("value", ["123456", "1" * 14, "22 123456", "07700-900123"])
def test_valid_phone(value):
    _, errors = register(phone=value)
    assert errors == {}


# --- email --------------------------------------------------------------------------

INVALID_EMAIL = "Please enter a valid email address (e.g. name@example.com)."


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "Email is required."),
        ("plainaddress", INVALID_EMAIL),
        ("@example.com", INVALID_EMAIL),
        ("name@", INVALID_EMAIL),
        ("name@example", INVALID_EMAIL),
        ("name@example.c", INVALID_EMAIL),
        ("name@@example.com", INVALID_EMAIL),
        ("name..dots@example.com", INVALID_EMAIL),
        (".name@example.com", INVALID_EMAIL),
        ("name@-example.com", INVALID_EMAIL),
        ("name@exa mple.com", INVALID_EMAIL),
        ("name@example.com<script>", INVALID_EMAIL),
        ("x" * 65 + "@example.com", INVALID_EMAIL),
        ("x" * 64 + "@" + "d" * 186 + ".com", "Email must be at most 254 characters."),
    ],
)
def test_invalid_email(value, message):
    assert error_for("email", email=value) == message


@pytest.mark.parametrize(
    "value",
    [
        "name@example.com",
        "first.last@example.co.uk",
        "name+tag@sub.example.gr",
        "o'brien@example.ie",
        "x" * 64 + "@example.com",
    ],
)
def test_valid_email(value):
    _, errors = register(email=value)
    assert errors == {}


# --- password -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "Password is required."),
        ("Ab1#", "Password must be at least 8 characters."),
        ("A1#" + "a" * 126, "Password must be at most 128 characters."),
        ("secret#123", "Password must include at least one capital letter."),
        ("Secret#abc", "Password must include at least one number."),
        ("Secret1234", "Password must include at least one symbol."),
        ("Secret 1234", "Password must include at least one symbol."),  # space isn't a symbol
        ("secretabc", "Password must include at least one capital letter, one number and one symbol."),
        ("SECRETABC", "Password must include at least one number and one symbol."),
    ],
)
def test_invalid_password(value, message):
    assert error_for("password", password=value) == message


@pytest.mark.parametrize("value", ["Secret#123", "Ωmega_2024", "Pa$$w0rd", "A1#" + "a" * 125])
def test_valid_password(value):
    _, errors = register(password=value)
    assert errors == {}


# --- terms --------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["", None])
def test_terms_must_be_accepted(value):
    assert (
        error_for("terms", terms=value)
        == "You must accept the Privacy Policy and Terms and Conditions."
    )


# --- login --------------------------------------------------------------------------


def test_valid_login():
    data, errors = validate_login({"email": " Ioannis@Example.com ", "password": "anything"})
    assert errors == {}
    assert data == LoginCredentials(email="ioannis@example.com", password="anything")


def test_login_does_not_enforce_password_policy():
    _, errors = validate_login({"email": "a@example.com", "password": "weak"})
    assert errors == {}


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ({}, {"email": "Email is required.", "password": "Password is required."}),
        ({"email": "not-an-email", "password": "x"}, {"email": INVALID_EMAIL}),
        ({"email": "a@example.com", "password": "x" * 129}, {"password": "Invalid email or password."}),
    ],
)
def test_invalid_login(form, expected):
    data, errors = validate_login(form)
    assert data is None
    assert errors == expected
