import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from countries.models import Country

pytestmark = pytest.mark.django_db


def test_countries_are_seeded_by_migration():
    rows = Country.objects.values_list("iso_code", "name", "dial_code")
    assert list(rows) == [
        ("CY", "Cyprus", "357"),
        ("GR", "Greece", "30"),
        ("GB", "United Kingdom", "44"),
    ]  # ordered by name


def test_str_shows_dial_code(greece):
    assert str(greece) == "Greece (+30)"


@pytest.mark.parametrize("dial_code", ["", "+30", "3a", "12345"])
def test_dial_code_must_be_1_to_4_digits(dial_code):
    with pytest.raises(IntegrityError, match="countries_country_dial_code_digits"):
        Country.objects.create(iso_code="FR", name="France", dial_code=dial_code)


@pytest.mark.parametrize("iso_code", ["F", "FRA"])
def test_iso_code_must_be_two_characters(iso_code):
    with pytest.raises(IntegrityError, match="countries_country_iso_code_length"):
        Country.objects.create(iso_code=iso_code, name="France", dial_code="33")


def test_iso_code_is_unique():
    with pytest.raises(IntegrityError, match="UNIQUE"):
        Country.objects.create(iso_code="GR", name="Another Greece", dial_code="30")


def test_dial_code_may_be_shared():
    # +1 is used by the US and Canada alike.
    Country.objects.create(iso_code="US", name="United States", dial_code="1")
    Country.objects.create(iso_code="CA", name="Canada", dial_code="1")


def test_country_with_customers_cannot_be_deleted(make_customer, greece):
    make_customer()
    with pytest.raises(ProtectedError):
        greece.delete()
