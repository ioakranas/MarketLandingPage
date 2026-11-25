"""Login use case: Django's authentication, plus account lockout and login history.

Django already provides the hard parts, so we don't re-implement them:
- the password check (constant time, Argon2) and the automatic upgrade of outdated
  hashes on a successful login;
- timing-attack mitigation: for an unknown email it still hashes the password, so
  "no such account" takes as long as "wrong password".

This module adds what Django doesn't have: lockout after repeated failures, and a
record of every attempt on an existing account.
"""

import logging
import math
from datetime import datetime, timedelta

from django.contrib.auth import authenticate
from django.utils import timezone

from accounts.models import User
from authentication.models import LoginAttempt
from authentication.selectors import lockout_remaining
from common.privacy import mask_email
from common.validation import LoginCredentials

logger = logging.getLogger(__name__)


class InvalidCredentials(Exception):
    """Unknown email or wrong password: deliberately the same error for both."""


class AccountLocked(Exception):
    def __init__(self, retry_after: timedelta):
        super().__init__(f"Account locked for another {retry_after}")
        self.retry_after = retry_after

    @property
    def minutes_remaining(self) -> int:
        """Rounded up: "1 minute" until the very last second."""
        return max(1, math.ceil(self.retry_after.total_seconds() / 60))


def authenticate_customer(credentials: LoginCredentials, ip_address: str | None) -> User:
    """Return the user if the credentials are valid and the account is not locked.

    Raises InvalidCredentials or AccountLocked. Starting the session is the caller's
    job (the API view calls django.contrib.auth.login).
    """
    now = _now()
    user = User.objects.filter(email__iexact=credentials.email).first()

    # Checked before the password: while locked, guesses are not even evaluated.
    if user is not None and (retry_after := lockout_remaining(user, now)):
        logger.warning("Login attempt on locked account %s from %s", user.pk, ip_address)
        raise AccountLocked(retry_after)

    authenticated = authenticate(username=credentials.email, password=credentials.password)
    if authenticated is None:
        if user is None:
            logger.warning(
                "Failed login for unknown email %s from %s",
                mask_email(credentials.email),
                ip_address,
            )
        else:
            # Wrong password, or an inactive account (which never logs in).
            _record_attempt(user, succeeded=False, ip_address=ip_address, at=now)
        raise InvalidCredentials

    _record_attempt(authenticated, succeeded=True, ip_address=ip_address, at=now)
    return authenticated


def purge_failed_login_attempts(older_than: timedelta) -> int:
    """Retention: delete failed attempts older than the given age. Returns rows deleted.

    Successful logins are kept: they are the customer's login history.
    """
    deleted, _ = LoginAttempt.objects.filter(
        succeeded=False, attempted_at__lt=_now() - older_than
    ).delete()
    return deleted


def _record_attempt(user: User, *, succeeded: bool, ip_address: str | None, at: datetime) -> None:
    LoginAttempt.objects.create(
        user=user, succeeded=succeeded, ip_address=ip_address, attempted_at=at
    )


def _now() -> datetime:
    """Single clock for this module, replaceable in tests."""
    return timezone.now()
