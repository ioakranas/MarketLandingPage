import pytest

from countries.models import Country

pytestmark = pytest.mark.django_db


def test_digits_only_filters_like_the_constraint():
    assert set(Country.objects.filter(dial_code__digits_only=True).values_list("iso_code", flat=True)) == {
        "GR", "CY", "GB",
    }


def test_length_lookup():
    assert list(Country.objects.filter(dial_code__length=3).values_list("iso_code", flat=True)) == ["CY"]


def test_digits_only_accepts_only_true():
    with pytest.raises(ValueError, match="only supports the value True"):
        list(Country.objects.filter(dial_code__digits_only=False))
