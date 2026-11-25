"""Server-side validation: the source of truth for every input rule.

Pure functions with no Flask or database dependency. Each validator returns either the
cleaned (normalised) data or a dict of ``field -> error message``, one specific message
per invalid field.

Messages, labels, limits and the email pattern are defined once here and also handed to
the browser (see ``client_config``), so the front-end gives instant feedback with exactly
the same rules and wording. Only this module decides what is accepted.
"""

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

# Limits are shared with the CHECK constraints in schema.sql.
LIMITS = {
    "name_min_exclusive": 3,  # requirement: "length > 3"
    "name_max": 50,
    "phone_min": 6,
    "phone_max": 14,
    "email_max": 254,  # RFC 5321 limit for a forward path
    "email_local_max": 64,
    "password_min": 8,
    "password_max": 128,  # bounds the hashing cost of a single request
}

LABELS = {
    "first_name": "First name",
    "last_name": "Last name",
    "phone_code": "Country code",
    "phone": "Phone number",
    "email": "Email",
    "password": "Password",
}

MESSAGES = {
    "required": "{label} is required.",
    "name_too_short": "{label} must be longer than {min} characters.",
    "name_too_long": "{label} must be at most {max} characters.",
    "name_characters": "{label} may only contain letters, spaces, hyphens and apostrophes.",
    "name_latin": "{label} must be written in Latin characters, as shown in your passport.",
    "name_edges": "{label} must start and end with a letter.",
    "country_required": "Please select a country.",
    "country_invalid": "Please select a valid country.",
    "code_numeric": "Country code must be numeric (e.g. 30).",
    "code_mismatch": "Country code does not match the selected country.",
    "phone_digits": "Phone number may only contain digits.",
    "phone_length": "Phone number must be between {min} and {max} digits.",
    "email_too_long": "Email must be at most {max} characters.",
    "email_invalid": "Please enter a valid email address (e.g. name@example.com).",
    "password_too_short": "Password must be at least {min} characters.",
    "password_too_long": "Password must be at most {max} characters.",
    "password_missing": "Password must include at least {missing}.",
    "terms_required": "You must accept the Privacy Policy and Terms and Conditions.",
}

PASSWORD_REQUIREMENTS = {
    "capital": "one capital letter",
    "number": "one number",
    "symbol": "one symbol",
}

# Pragmatic email check: one '@', a non-empty local part and a dotted domain with a
# 2+ letter TLD. Full RFC 5322 compliance is neither practical nor desirable for a
# sign-up form; real ownership is proven by a confirmation email in production.
# Written in the common subset of Python and JavaScript regex syntax: the browser
# compiles this exact string.
EMAIL_PATTERN_SOURCE = (
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"  # local part
    r"@([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"  # domain
)
EMAIL_PATTERN = re.compile(EMAIL_PATTERN_SOURCE)
# Requirement: "country code numeric". Digits only; the '+' is purely presentational.
DIAL_CODE_PATTERN = re.compile(r"^[0-9]{1,4}$")
DIGITS_PATTERN = re.compile(r"^[0-9]+$")
PHONE_SEPARATORS = re.compile(r"[\s-]")

NAME_SEPARATORS = frozenset(" -'")


@dataclass(frozen=True)
class Registration:
    first_name: str
    last_name: str
    country_iso: str
    phone: str
    email: str
    password: str


@dataclass(frozen=True)
class LoginCredentials:
    email: str
    password: str


Errors = dict[str, str]


# --- public API -----------------------------------------------------------------------


def validate_registration(
    form: Mapping[str, str], dial_codes: Mapping[str, str]
) -> tuple[Registration | None, Errors]:
    """Validate the sign-up form.

    ``dial_codes`` maps the allowed country ISO codes to their dial code
    (e.g. ``{"GR": "30"}``); it comes from the countries table.
    """
    errors: Errors = {}

    first_name = _check(errors, "first_name", _validate_name, form.get("first_name"), "first_name")
    last_name = _check(errors, "last_name", _validate_name, form.get("last_name"), "last_name")
    country_iso = _check(errors, "country", _validate_country, form.get("country"), dial_codes)
    # Without a valid country we can still check the code is numeric, just not that it matches.
    expected_code = dial_codes.get(country_iso) if country_iso else None
    _check(errors, "phone_code", _validate_phone_code, form.get("phone_code"), expected_code)
    phone = _check(errors, "phone", _validate_phone, form.get("phone"))
    email = _check(errors, "email", _validate_email, form.get("email"))
    password = _check(errors, "password", _validate_new_password, form.get("password"))
    if not form.get("terms"):
        errors["terms"] = _message("terms_required")

    if errors:
        return None, errors
    return Registration(first_name, last_name, country_iso, phone, email, password), {}


def validate_login(form: Mapping[str, str]) -> tuple[LoginCredentials | None, Errors]:
    """Validate the login form: email format and a non-empty password.

    Password complexity is deliberately *not* checked here: it would reveal the
    policy, and the stored hash is the only thing that decides.
    """
    errors: Errors = {}

    email = _check(errors, "email", _validate_email, form.get("email"))
    password = form.get("password") or ""
    if not password:
        errors["password"] = _message("required", label=LABELS["password"])
    elif len(password) > LIMITS["password_max"]:
        errors["password"] = "Invalid email or password."

    if errors:
        return None, errors
    return LoginCredentials(email, password), {}


def password_policy_error(password: str | None) -> str | None:
    """The password policy alone, for every way a password is set (see common.passwords)."""
    try:
        _validate_new_password(password)
    except _Invalid as error:
        return str(error)
    return None


def password_policy_summary() -> str:
    """E.g. "8-128 characters, including one capital letter, one number and one symbol." """
    requirements = _join(list(PASSWORD_REQUIREMENTS.values()))
    return f"{LIMITS['password_min']}-{LIMITS['password_max']} characters, including {requirements}."


def client_config() -> dict:
    """Everything the browser needs to mirror these rules, rendered into the page as JSON."""
    return {
        "limits": LIMITS,
        "labels": LABELS,
        "messages": MESSAGES,
        "passwordRequirements": PASSWORD_REQUIREMENTS,
        "emailPattern": EMAIL_PATTERN_SOURCE,
    }


# --- helpers ------------------------------------------------------------------------


class _Invalid(Exception):
    """Raised by a field validator; carries the user-facing message."""


def _message(key: str, **params) -> str:
    return MESSAGES[key].format(**params)


def _check(errors: Errors, field: str, validator, value, *args):
    """Run one field validator, recording its message under ``field`` on failure."""
    try:
        return validator(value, *args)
    except _Invalid as error:
        errors[field] = str(error)
        return None


def _validate_name(value: str | None, field: str) -> str:
    label = LABELS[field]
    # NFC normalisation makes "é" one character whether it was typed as one code point
    # or as "e" + combining accent, so length and letter checks behave consistently.
    name = unicodedata.normalize("NFC", (value or "").strip())
    if not name:
        raise _Invalid(_message("required", label=label))
    if len(name) <= LIMITS["name_min_exclusive"]:
        raise _Invalid(_message("name_too_short", label=label, min=LIMITS["name_min_exclusive"]))
    if len(name) > LIMITS["name_max"]:
        raise _Invalid(_message("name_too_long", label=label, max=LIMITS["name_max"]))
    if not all(char.isalpha() or char in NAME_SEPARATORS for char in name):
        raise _Invalid(_message("name_characters", label=label))
    if not all(_is_latin(char) for char in name if char.isalpha()):
        raise _Invalid(_message("name_latin", label=label))
    if not (name[0].isalpha() and name[-1].isalpha()):
        raise _Invalid(_message("name_edges", label=label))
    return name


def _validate_country(value: str | None, dial_codes: Mapping[str, str]) -> str:
    iso = (value or "").strip().upper()
    if not iso:
        raise _Invalid(_message("country_required"))
    if iso not in dial_codes:
        raise _Invalid(_message("country_invalid"))
    return iso


def _validate_phone_code(value: str | None, expected: str | None) -> str:
    code = (value or "").strip()
    if not code:
        raise _Invalid(_message("required", label=LABELS["phone_code"]))
    if not DIAL_CODE_PATTERN.match(code):
        raise _Invalid(_message("code_numeric"))
    if expected is not None and code != expected:
        raise _Invalid(_message("code_mismatch"))
    return code


def _validate_phone(value: str | None) -> str:
    # Users naturally type "691 234 5678" or "691-234-5678"; we store digits only.
    phone = PHONE_SEPARATORS.sub("", value or "")
    if not phone:
        raise _Invalid(_message("required", label=LABELS["phone"]))
    if not DIGITS_PATTERN.match(phone):
        raise _Invalid(_message("phone_digits"))
    if not LIMITS["phone_min"] <= len(phone) <= LIMITS["phone_max"]:
        raise _Invalid(_message("phone_length", min=LIMITS["phone_min"], max=LIMITS["phone_max"]))
    return phone


def _validate_email(value: str | None) -> str:
    email = (value or "").strip()
    if not email:
        raise _Invalid(_message("required", label=LABELS["email"]))
    if len(email) > LIMITS["email_max"]:
        raise _Invalid(_message("email_too_long", max=LIMITS["email_max"]))
    local_part = email.rpartition("@")[0]
    if not EMAIL_PATTERN.match(email) or len(local_part) > LIMITS["email_local_max"]:
        raise _Invalid(_message("email_invalid"))
    # Stored lower-case: providers treat addresses case-insensitively in practice.
    return email.lower()


def _validate_new_password(value: str | None) -> str:
    password = value or ""
    if not password:
        raise _Invalid(_message("required", label=LABELS["password"]))
    if len(password) < LIMITS["password_min"]:
        raise _Invalid(_message("password_too_short", min=LIMITS["password_min"]))
    if len(password) > LIMITS["password_max"]:
        raise _Invalid(_message("password_too_long", max=LIMITS["password_max"]))

    missing = []
    if not any(char.isupper() for char in password):
        missing.append(PASSWORD_REQUIREMENTS["capital"])
    if not any(char in "0123456789" for char in password):
        missing.append(PASSWORD_REQUIREMENTS["number"])
    if not any(_is_symbol(char) for char in password):
        missing.append(PASSWORD_REQUIREMENTS["symbol"])
    if missing:
        raise _Invalid(_message("password_missing", missing=_join(missing)))
    return password


def _is_latin(letter: str) -> bool:
    """True for Latin letters, accented ones included (e, é, ñ, ß, Ç).

    Names must match identity documents for KYC/AML, whose machine-readable zone is
    Latin-only, and payment rails (SEPA/SWIFT) restrict character sets. Rejecting other
    scripts also prevents look-alike spoofing (Cyrillic 'а' vs Latin 'a').
    """
    return unicodedata.name(letter, "").startswith("LATIN ")


def _is_symbol(char: str) -> bool:
    return not char.isalnum() and not char.isspace()


def _join(items: list[str]) -> str:
    """["a"] -> "a";  ["a", "b"] -> "a and b";  ["a", "b", "c"] -> "a, b and c"."""
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"
