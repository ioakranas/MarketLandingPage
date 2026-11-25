"""Shared fixtures (pytest discovers this file automatically)."""

import pytest

from accounts.models import User
from countries.models import Country
from customers.models import Customer

PASSWORD = "Secret#123"


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    """Argon2 is deliberately slow (100 MB, several passes). Tests use the same algorithm
    with tiny parameters so the suite stays fast; the production settings are covered
    by tests/test_settings.py."""
    settings.PASSWORD_HASHERS = ["tests.hashers.FastArgon2PasswordHasher"]


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def greece(db):
    """Seeded by the countries data migration."""
    return Country.objects.get(iso_code="GR")


@pytest.fixture
def make_user(db):
    def make(email="ioannis@example.com", password=PASSWORD, **extra):
        return User.objects.create_user(email, password, **extra)

    return make


@pytest.fixture
def make_customer(make_user, greece):
    def make(email="ioannis@example.com", **fields):
        values = {
            "first_name": "Ioannis",
            "last_name": "Papadopoulos",
            "country": greece,
            "phone": "6912345678",
            **fields,
        }
        return Customer.objects.create(user=make_user(email), **values)

    return make
