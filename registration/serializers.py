"""Request and response shapes of the registration API (the DTOs).

The fields describe the contract (types, which feeds the OpenAPI schema); the rules
and messages come from common.validation, the single source shared with the web page.
"""

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from common.passwords import password_validators_error
from common.serializers import raw_text
from common.validation import Registration, password_policy_summary, validate_registration
from countries.selectors import dial_codes
from customers.models import Customer


@extend_schema_serializer(component_name="Registration")  # -> "RegistrationRequest"
class RegistrationRequestSerializer(serializers.Serializer):
    first_name = raw_text(help_text="Latin letters, longer than 3 characters.")
    last_name = raw_text(help_text="Latin letters, longer than 3 characters.")
    country = raw_text(help_text="ISO 3166-1 alpha-2 code, e.g. GR (see /api/v1/countries).")
    phone_code = raw_text(help_text="Dial code of the selected country, digits only, e.g. 30.")
    phone = raw_text(help_text="National number, 6-14 digits (spaces and dashes are ignored).")
    email = raw_text()
    password = raw_text(
        write_only=True,
        style={"input_type": "password"},
        # Same wording as the admin's password help (one source: common.validation).
        help_text=password_policy_summary() + " Common passwords are rejected.",
    )
    terms = serializers.BooleanField(
        required=False, default=False, help_text="Acceptance of the Privacy Policy and Terms."
    )

    def validate(self, attrs) -> Registration:
        registration, errors = validate_registration(attrs, dial_codes())
        if "password" not in errors:
            # The policy passed; now the checks shared with staff accounts (common
            # passwords, similarity to the email). Server-side only: the browser
            # doesn't download the blocklist.
            if message := password_validators_error(attrs["password"], attrs.get("email")):
                errors["password"] = message
        if errors:
            raise serializers.ValidationError(errors)
        return registration


class CustomerResponseSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    country = serializers.CharField(source="country.iso_code")

    class Meta:
        model = Customer
        # No "id": the client never needs it, and sequential keys would leak how many
        # customers there are. A public id would be a UUID, never the primary key.
        fields = ["email", "first_name", "last_name", "country", "phone", "created_at"]
