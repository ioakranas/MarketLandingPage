import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError

from accounts.models import User
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_create_user_normalises_email_and_hashes_password(make_user):
    user = make_user(email="  Ioannis@Example.COM ")

    assert user.email == "ioannis@example.com"
    assert user.password.startswith("argon2$argon2id$")
    assert PASSWORD not in user.password
    assert user.check_password(PASSWORD)
    assert not user.is_staff and user.is_active


def test_same_password_gets_different_hashes(make_user):
    first = make_user(email="a@example.com")
    second = make_user(email="b@example.com")
    assert first.password != second.password  # random salt per hash


def test_email_is_required():
    with pytest.raises(ValueError, match="email address is required"):
        User.objects.create_user("", PASSWORD)


def test_create_superuser_sets_staff_flags():
    admin = User.objects.create_superuser("admin@example.com", PASSWORD)
    assert admin.is_staff and admin.is_superuser


def test_login_lookup_is_case_insensitive(make_user):
    user = make_user()
    assert authenticate(username="IOANNIS@example.com", password=PASSWORD) == user


def test_email_unique_case_insensitive_at_database_level(make_user):
    make_user(email="ioannis@example.com")
    # Bypasses the manager's normalisation: only the database constraint stands in the way.
    with pytest.raises(IntegrityError, match="accounts_user_email_ci_unique|UNIQUE"):
        User.objects.create(email="IOANNIS@example.com", password="x")


@pytest.mark.parametrize("email", ["not-an-email", "x" * 250 + "@x.gr"])
def test_email_format_checked_at_database_level(email):
    with pytest.raises(IntegrityError, match="CHECK constraint failed: accounts_user_email_format"):
        User.objects.create(email=email, password="x")


def test_str_is_the_email(make_user):
    assert str(make_user()) == "ioannis@example.com"
