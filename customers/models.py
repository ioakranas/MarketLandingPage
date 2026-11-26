"""The customer: personal data of a registered person, linked one-to-one to the
login identity (accounts.User)."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.validation import LIMITS, MESSAGES, validate_profile


def _name_length(field: str) -> Q:
    return Q(**{
        f"{field}__length__gt": LIMITS["name_min_exclusive"],
        f"{field}__length__lte": LIMITS["name_max"],
    })


class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer"
    )
    first_name = models.CharField(max_length=LIMITS["name_max"])
    last_name = models.CharField(max_length=LIMITS["name_max"])
    # PROTECT: a country that customers reference cannot be deleted.
    country = models.ForeignKey(
        "countries.Country", on_delete=models.PROTECT, related_name="customers"
    )
    # National number, digits only; the dial code follows from the country.
    phone = models.CharField(max_length=LIMITS["phone_max"])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Last line of defence: the application validates first (with friendly
        # messages); these guarantee no code path can store invalid data.
        constraints = [
            models.CheckConstraint(
                condition=_name_length("first_name"),
                name="customers_customer_first_name_length",
                violation_error_message="First name must be between 4 and 50 characters.",
            ),
            models.CheckConstraint(
                condition=_name_length("last_name"),
                name="customers_customer_last_name_length",
                violation_error_message="Last name must be between 4 and 50 characters.",
            ),
            models.CheckConstraint(
                condition=Q(
                    phone__digits_only=True,
                    phone__length__gte=LIMITS["phone_min"],
                    phone__length__lte=LIMITS["phone_max"],
                ),
                name="customers_customer_phone_format",
                violation_error_message=MESSAGES["phone_length"].format(
                    min=LIMITS["phone_min"], max=LIMITS["phone_max"]
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def clean(self) -> None:
        """Model validation (run by the admin's forms): the same rules and messages as
        sign-up, so every way of editing a customer accepts exactly the same data."""
        cleaned, errors = validate_profile(self.first_name, self.last_name, self.phone)
        if errors:
            raise ValidationError(errors)
        for field, value in cleaned.items():
            setattr(self, field, value)  # e.g. "99 123 456" -> "99123456"
