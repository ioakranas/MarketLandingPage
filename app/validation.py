"""Server-side validation: the source of truth for every input rule.

Pure functions with no Flask or database dependency. Each validator returns either the
cleaned (normalised) data or a dict of ``field -> error message``, one specific message
per invalid field. The front-end mirrors these rules for instant feedback, but only
this module decides what is accepted.
"""

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

# Limits are shared with the CHECK constraints in schema.sql.
NAME_MIN_LENGTH_EXCLUSIVE = 3  # requirement: "length > 3"
NAME_MAX_LENGTH = 50
PHONE_MIN_DIGITS = 6
PHONE_MAX_DIGITS = 14
EMAIL_MAX_LENGTH = 254  # RFC 5321 limit for a forward path
EMAIL_LOCAL_MAX_LENGTH = 64
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128  # bounds the hashing cost of a single request

NAME_SEPARATORS = frozenset(" -'")

# Pragmatic email check: one '@', a non-empty local part and a dotted domain with a
# 2+ letter TLD. Full RFC 5322 compliance is neither practical nor desirable for a
# sign-up form; real ownership is proven by a confirmation email in production.
EMAIL_PATTERN = re.compile(
    r"""
    ^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*  # local part
    @
    ([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$             # domain
    """,
    re.VERBOSE,
)
# Requirement: "country code numeric". Digits only; the '+' is purely presentational.
DIAL_CODE_PATTERN = re.compile(r"^[0-9]{1,4}$")
DIGITS_PATTERN = re.compile(r"^[0-9]+$")
PHONE_SEPARATORS = re.compile(r"[\s-]")


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

    first_name = _check(errors, "first_name", _validate_name, form.get("first_name"), "First name")
    last_name = _check(errors, "last_name", _validate_name, form.get("last_name"), "Last name")
    country_iso = _check(errors, "country", _validate_country, form.get("country"), dial_codes)
    # Without a valid country we can still check the code is numeric, just not that it matches.
    expected_code = dial_codes.get(country_iso) if country_iso else None
    _check(errors, "phone_code", _validate_phone_code, form.get("phone_code"), expected_code)
    phone = _check(errors, "phone", _validate_phone, form.get("phone"))
    email = _check(errors, "email", _validate_email, form.get("email"))
    password = _check(errors, "password", _validate_new_password, form.get("password"))
    if not form.get("terms"):
        errors["terms"] = "You must accept the Privacy Policy and Terms and Conditions."

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
        errors["password"] = "Password is required."
    elif len(password) > PASSWORD_MAX_LENGTH:
        errors["password"] = "Invalid email or password."

    if errors:
        return None, errors
    return LoginCredentials(email, password), {}


# --- helpers ------------------------------------------------------------------------


class _Invalid(Exception):
    """Raised by a field validator; carries the user-facing message."""


def _check(errors: Errors, field: str, validator, value, *args):
    """Run one field validator, recording its message under ``field`` on failure."""
    try:
        return validator(value, *args)
    except _Invalid as error:
        errors[field] = str(error)
        return None


def _validate_name(value: str | None, label: str) -> str:
    # NFC normalisation makes "é" one character whether it was typed as one code point
    # or as "e" + combining accent, so length and letter checks behave consistently.
    name = unicodedata.normalize("NFC", (value or "").strip())
    if not name:
        raise _Invalid(f"{label} is required.")
    if len(name) <= NAME_MIN_LENGTH_EXCLUSIVE:
        raise _Invalid(f"{label} must be longer than {NAME_MIN_LENGTH_EXCLUSIVE} characters.")
    if len(name) > NAME_MAX_LENGTH:
        raise _Invalid(f"{label} must be at most {NAME_MAX_LENGTH} characters.")
    if not all(char.isalpha() or char in NAME_SEPARATORS for char in name):
        raise _Invalid(f"{label} may only contain letters, spaces, hyphens and apostrophes.")
    if not all(_is_latin(char) for char in name if char.isalpha()):
        raise _Invalid(f"{label} must be written in Latin characters, as shown in your passport.")
    if not (name[0].isalpha() and name[-1].isalpha()):
        raise _Invalid(f"{label} must start and end with a letter.")
    return name


def _validate_country(value: str | None, dial_codes: Mapping[str, str]) -> str:
    iso = (value or "").strip().upper()
    if not iso:
        raise _Invalid("Please select a country.")
    if iso not in dial_codes:
        raise _Invalid("Please select a valid country.")
    return iso


def _validate_phone_code(value: str | None, expected: str | None) -> str:
    code = (value or "").strip()
    if not code:
        raise _Invalid("Country code is required.")
    if not DIAL_CODE_PATTERN.match(code):
        raise _Invalid("Country code must be numeric (e.g. 30).")
    if expected is not None and code != expected:
        raise _Invalid("Country code does not match the selected country.")
    return code


def _validate_phone(value: str | None) -> str:
    # Users naturally type "691 234 5678" or "691-234-5678"; we store digits only.
    phone = PHONE_SEPARATORS.sub("", value or "")
    if not phone:
        raise _Invalid("Phone number is required.")
    if not DIGITS_PATTERN.match(phone):
        raise _Invalid("Phone number may only contain digits.")
    if not PHONE_MIN_DIGITS <= len(phone) <= PHONE_MAX_DIGITS:
        raise _Invalid(
            f"Phone number must be between {PHONE_MIN_DIGITS} and {PHONE_MAX_DIGITS} digits."
        )
    return phone


def _validate_email(value: str | None) -> str:
    email = (value or "").strip()
    if not email:
        raise _Invalid("Email is required.")
    if len(email) > EMAIL_MAX_LENGTH:
        raise _Invalid(f"Email must be at most {EMAIL_MAX_LENGTH} characters.")
    local_part = email.rpartition("@")[0]
    if not EMAIL_PATTERN.match(email) or len(local_part) > EMAIL_LOCAL_MAX_LENGTH:
        raise _Invalid("Please enter a valid email address (e.g. name@example.com).")
    # Stored lower-case: providers treat addresses case-insensitively in practice.
    return email.lower()


def _validate_new_password(value: str | None) -> str:
    password = value or ""
    if not password:
        raise _Invalid("Password is required.")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise _Invalid(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise _Invalid(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")

    missing = []
    if not any(char.isupper() for char in password):
        missing.append("one capital letter")
    if not any(char in "0123456789" for char in password):
        missing.append("one number")
    if not any(_is_symbol(char) for char in password):
        missing.append("one symbol")
    if missing:
        raise _Invalid(f"Password must include at least {_join(missing)}.")
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
