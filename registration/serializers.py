"""Request and response shapes of the registration API (the DTOs).

The fields describe the contract (types, which feeds the OpenAPI schema); the rules
and messages come from common.validation, the single source shared with the web page.
"""

from rest_framework import serializers

from common.validation import Registration, validate_registration
from countries.selectors import dial_codes
from customers.models import Customer


def _text(**kwargs) -> serializers.CharField:
    # Not required and no trimming at this level: the validation layer reports missing
    # values with its own messages and decides what to trim (never the password).
    return serializers.CharField(required=False, allow_blank=True, trim_whitespace=False, **kwargs)


class RegistrationRequestSerializer(serializers.Serializer):
    first_name = _text(help_text="Latin letters, longer than 3 characters.")
    last_name = _text(help_text="Latin letters, longer than 3 characters.")
    country = _text(help_text="ISO 3166-1 alpha-2 code, e.g. GR (see /api/v1/countries).")
    phone_code = _text(help_text="Dial code of the selected country, digits only, e.g. 30.")
    phone = _text(help_text="National number, 6-14 digits (spaces and dashes are ignored).")
    email = _text()
    password = _text(
        write_only=True,
        style={"input_type": "password"},
        help_text="8-128 characters with at least one capital letter, one number and one symbol.",
    )
    terms = serializers.BooleanField(
        required=False, default=False, help_text="Acceptance of the Privacy Policy and Terms."
    )

    def validate(self, attrs) -> Registration:
        registration, errors = validate_registration(attrs, dial_codes())
        if errors:
            raise serializers.ValidationError(errors)
        return registration


class CustomerResponseSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    country = serializers.CharField(source="country.iso_code")

    class Meta:
        model = Customer
        fields = ["id", "email", "first_name", "last_name", "country", "phone", "created_at"]
