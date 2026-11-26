"""One password policy for every account, customer or staff.

Django runs settings.AUTH_PASSWORD_VALIDATORS wherever it sets a password (admin
"Add user", password changes, createsuperuser). PasswordPolicyValidator plugs our
rules (common.validation) into that list, and the registration API runs the same list,
so customers and staff meet the same bar, including Django's blocklist of ~20,000
common passwords (NIST SP 800-63B recommends checking against breached/common lists).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from common.validation import password_policy_error, password_policy_summary


class PasswordPolicyValidator:
    """settings.AUTH_PASSWORD_VALIDATORS entry for the rules in common.validation."""

    def validate(self, password: str, user=None) -> None:
        if error := password_policy_error(password):
            raise ValidationError(error, code="password_policy")

    def get_help_text(self) -> str:
        return password_policy_summary()


def password_validators_error(password: str, email: str | None = None) -> str | None:
    """First message from settings.AUTH_PASSWORD_VALIDATORS, or None if the password passes.

    ``email`` lets the similarity check reject passwords like "ioannis@example1".
    """
    # Unsaved user: the similarity check reads its attributes, nothing is stored.
    user = get_user_model()(email=email) if email else None
    try:
        validate_password(password, user=user)
    except ValidationError as error:
        return error.messages[0]
    return None
