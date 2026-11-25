"""manage.py purge_login_attempts"""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from authentication.models import LoginAttempt

pytestmark = pytest.mark.django_db


def run(*args) -> str:
    out = StringIO()
    call_command("purge_login_attempts", *args, stdout=out)
    return out.getvalue()


def test_purges_failures_older_than_the_given_days(customer, clock):
    LoginAttempt.objects.create(user=customer.user, succeeded=False, attempted_at=clock.now)
    clock.advance(days=8)

    assert run("--days", "7") == "Deleted 1 failed login attempt(s) older than 7 day(s).\n"
    assert not LoginAttempt.objects.exists()


def test_default_retention_is_30_days(customer, clock):
    LoginAttempt.objects.create(user=customer.user, succeeded=False, attempted_at=clock.now)
    clock.advance(days=8)

    assert run() == "Deleted 0 failed login attempt(s) older than 30 day(s).\n"


def test_days_must_be_positive():
    with pytest.raises(CommandError, match="at least 1"):
        run("--days", "0")
