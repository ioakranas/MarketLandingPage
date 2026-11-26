"""The registration use case, without HTTP."""

import pytest
from django.db import IntegrityError

from accounts.models import User
from common.validation import Registration
from customers.models import Customer
from registration import services
from registration.services import EmailAlreadyRegistered, register_customer

pytestmark = pytest.mark.django_db

REGISTRATION = Registration(
    first_name="Ioannis",
    last_name="Papadopoulos",
    country_iso="CY",
    phone="99123456",
    email="ioannis@example.com",
    password="Secret#123",
)


def test_creates_user_and_customer():
    customer = register_customer(REGISTRATION)

    assert customer.pk is not None
    assert customer.user.email == "ioannis@example.com"
    assert customer.country.iso_code == "CY"


def test_duplicate_email_raises_domain_error():
    register_customer(REGISTRATION)
    with pytest.raises(EmailAlreadyRegistered):
        register_customer(REGISTRATION)
    assert User.objects.count() == 1


def test_user_is_rolled_back_when_customer_cannot_be_created(monkeypatch):
    """Atomicity: no login identity without a customer profile."""

    def fail(**kwargs):
        raise IntegrityError("simulated failure")

    monkeypatch.setattr(Customer.objects, "create", fail)

    with pytest.raises(IntegrityError, match="simulated"):
        register_customer(REGISTRATION)
    assert not User.objects.exists()


def test_other_integrity_errors_are_not_mistaken_for_duplicates(monkeypatch):
    def fail(*args, **kwargs):
        raise IntegrityError("some other constraint")

    monkeypatch.setattr(services.User.objects, "create_user", fail)

    with pytest.raises(IntegrityError, match="some other constraint"):
        register_customer(REGISTRATION)
