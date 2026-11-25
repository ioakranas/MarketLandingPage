"""The customer: personal data of a registered person, linked one-to-one to the
login identity (accounts.User)."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.validation import LIMITS


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
                condition=_name_length("first_name"), name="customers_customer_first_name_length"
            ),
            models.CheckConstraint(
                condition=_name_length("last_name"), name="customers_customer_last_name_length"
            ),
            models.CheckConstraint(
                condition=Q(
                    phone__digits_only=True,
                    phone__length__gte=LIMITS["phone_min"],
                    phone__length__lte=LIMITS["phone_max"],
                ),
                name="customers_customer_phone_format",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"
