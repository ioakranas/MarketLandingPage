"""One password policy for customers and staff (settings.AUTH_PASSWORD_VALIDATORS)."""

import pytest
from django.contrib.auth.password_validation import password_validators_help_texts
from django.core.exceptions import ValidationError

from common.passwords import PasswordPolicyValidator, password_validators_error


def test_policy_validator_uses_the_same_messages_as_the_forms():
    with pytest.raises(ValidationError) as error:
        PasswordPolicyValidator().validate("secret#123")

    assert error.value.messages == ["Password must include at least one capital letter."]
    assert error.value.error_list[0].code == "password_policy"


def test_policy_validator_accepts_a_compliant_password():
    PasswordPolicyValidator().validate("Secret#123")


def test_help_text_summarises_the_policy():
    assert PasswordPolicyValidator().get_help_text() == (
        "8-128 characters, including one capital letter, one number and one symbol."
    )


def test_policy_is_part_of_djangos_validators():
    """So the admin forms and createsuperuser show and enforce it too."""
    assert password_validators_help_texts()[0] == PasswordPolicyValidator().get_help_text()


@pytest.mark.parametrize(
    ("password", "email", "message"),
    [
        ("1", None, "Password must be at least 8 characters."),
        ("Password1!", None, "This password is too common."),  # passes the policy
        ("Ioannis#1234", "ioannis@example.com", "The password is too similar to the email."),
        ("Secret#123", "ioannis@example.com", None),
    ],
)
def test_all_validators(password, email, message):
    assert password_validators_error(password, email) == message
