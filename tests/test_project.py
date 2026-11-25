"""Project-wide checks: migrations in sync with models, admin reachable."""

import pytest
from django.core.management import call_command
from django.db import connection

from accounts.models import User

pytestmark = pytest.mark.django_db


def test_no_missing_migrations():
    # Fails if a model was changed without generating its migration.
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


def test_constraints_are_plain_sql_in_the_schema():
    """Readable by any SQLite client, not dependent on Django-registered functions."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT sql FROM sqlite_master WHERE name = 'customers_customer'")
        ddl = cursor.fetchone()[0]
    assert "NOT GLOB '*[^0-9]*'" in ddl
    assert "LENGTH" in ddl.upper()
    assert "REGEXP" not in ddl.upper()


@pytest.fixture
def admin_client(client):
    client.force_login(User.objects.create_superuser("admin@example.com", "Secret#123"))
    return client


@pytest.mark.parametrize(
    "url",
    [
        "/admin/",
        "/admin/accounts/user/",
        "/admin/accounts/user/add/",
        "/admin/countries/country/",
        "/admin/customers/customer/",
    ],
)
def test_admin_pages_load_for_staff(admin_client, url):
    assert admin_client.get(url).status_code == 200


def test_admin_requires_staff(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response.headers["Location"]


def test_admin_can_create_a_user(admin_client):
    response = admin_client.post(
        "/admin/accounts/user/add/",
        {"email": "Staff@Example.com", "password1": "Secret#123x", "password2": "Secret#123x"},
    )
    assert response.status_code == 302
    assert User.objects.filter(email__iexact="staff@example.com").exists()
