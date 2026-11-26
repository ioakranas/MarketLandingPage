"""Database-level constraints on customers. Values are written with .create(), which
skips Django validation, so only the constraints in the schema can reject them."""

import pytest
from django.db import IntegrityError

from customers.models import Customer

pytestmark = pytest.mark.django_db


def test_valid_customer_is_stored(make_customer):
    customer = make_customer()
    stored = Customer.objects.select_related("user", "country").get(pk=customer.pk)

    assert stored.user.email == "ioannis@example.com"
    assert stored.country.iso_code == "GR"
    assert stored.created_at is not None
    assert str(stored) == "Ioannis Papadopoulos"


@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize("value", ["", "Ana", "x" * 51])
def test_name_length_rejected(make_customer, field, value):
    with pytest.raises(IntegrityError, match=f"customers_customer_{field}_length"):
        make_customer(**{field: value})


@pytest.mark.parametrize("value", ["Nick", "Ιωάννης", "x" * 50])
def test_name_length_boundaries_accepted(make_customer, value):
    # Length counts characters, not bytes: "Ιωάννης" is 7 characters (14 bytes in UTF-8).
    # (Latin-only is a validation-layer rule, not a database one.)
    make_customer(first_name=value, last_name=value)


@pytest.mark.parametrize("phone", ["12345", "1" * 15, "69123abc78", "+306912345", "691 234 567", ""])
def test_invalid_phone_rejected(make_customer, phone):
    with pytest.raises(IntegrityError, match="customers_customer_phone_format"):
        make_customer(phone=phone)


@pytest.mark.parametrize("phone", ["123456", "1" * 14])
def test_phone_length_boundaries_accepted(make_customer, phone):
    make_customer(phone=phone)


def test_one_customer_per_user(make_customer, greece):
    customer = make_customer()
    with pytest.raises(IntegrityError, match="UNIQUE"):
        Customer.objects.create(
            user=customer.user, first_name="Other", last_name="Person", country=greece,
            phone="6912345678",
        )


def test_deleting_the_user_deletes_the_customer(make_customer):
    customer = make_customer()
    customer.user.delete()
    assert not Customer.objects.exists()
