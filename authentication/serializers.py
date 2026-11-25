"""Request and response shapes of the session API."""

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from common.serializers import raw_text
from common.validation import LoginCredentials, validate_login


@extend_schema_serializer(component_name="Login")  # -> "LoginRequest"
class LoginRequestSerializer(serializers.Serializer):
    email = raw_text()
    password = raw_text(write_only=True, style={"input_type": "password"})

    def validate(self, attrs) -> LoginCredentials:
        credentials, errors = validate_login(attrs)
        if errors:
            raise serializers.ValidationError(errors)
        return credentials


class SessionResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(allow_null=True)
    last_name = serializers.CharField(allow_null=True)
    previous_login_at = serializers.DateTimeField(
        allow_null=True, help_text="The login before this one; null on the first login."
    )
