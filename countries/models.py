"""Reference data: the countries customers can register from.

Own app because it has its own lifecycle (maintained by back office through the admin,
not by customers) and several consumers (registration today; KYC, payments later).
"""

from django.db import models
from django.db.models import Q


class Country(models.Model):
    # ISO 3166-1 alpha-2: the stable public identifier (forms and APIs use it, never the id).
    iso_code = models.CharField(max_length=2, unique=True)
    name = models.CharField(max_length=100, unique=True)
    # Digits only; the leading '+' is presentation. Not unique: +1 is shared by the US,
    # Canada and others, which is why the country, not the dial code, identifies it.
    dial_code = models.CharField(max_length=4)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"
        constraints = [
            models.CheckConstraint(
                condition=Q(iso_code__length=2), name="countries_country_iso_code_length"
            ),
            models.CheckConstraint(
                condition=Q(dial_code__digits_only=True, dial_code__length__lte=4),
                name="countries_country_dial_code_digits",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} (+{self.dial_code})"
