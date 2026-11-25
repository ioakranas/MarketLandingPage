import pytest

from authentication.models import LoginAttempt
from tests.authentication.conftest import NOW

pytestmark = pytest.mark.django_db


def test_str_describes_the_attempt(customer):
    attempt = LoginAttempt(user=customer.user, succeeded=False, attempted_at=NOW)
    assert str(attempt) == f"Login failed for user {customer.user.pk} at 2026-11-24 12:00:00"


def test_deleting_the_account_deletes_its_attempts(customer):
    LoginAttempt.objects.create(user=customer.user, succeeded=True)
    customer.user.delete()
    assert not LoginAttempt.objects.exists()
