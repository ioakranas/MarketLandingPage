"""Read-only queries on countries (the 'selectors' half of the service layer)."""

from django.db.models import QuerySet

from countries.models import Country


def list_countries() -> QuerySet[Country]:
    return Country.objects.order_by("name")


def dial_codes() -> dict[str, str]:
    """{"GR": "30", ...}: the allowed countries, as the validation layer expects them."""
    return dict(Country.objects.values_list("iso_code", "dial_code"))
