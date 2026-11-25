"""Read side of authentication: lockout state and login history."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Subquery, Value
from django.db.models.functions import Coalesce

from accounts.models import User
from authentication.models import LoginAttempt
from customers.models import Customer


@dataclass(frozen=True)
class SessionSummary:
    """What the logged-in customer sees about their session.

    No internal ids: the client never needs them (it always acts as "me"), and
    sequential keys would leak how many customers there are.
    """

    email: str
    first_name: str | None  # None for staff accounts, which have no customer profile
    last_name: str | None
    # Shown after login as a security signal: "wasn't me?" -> report it.
    previous_login_at: datetime | None  # None on the first login


def lockout_remaining(user: User, now: datetime) -> timedelta | None:
    """How long the account stays locked, or None if it is not locked.

    Locked = at least LOGIN_LOCKOUT_THRESHOLD failures within LOGIN_LOCKOUT_WINDOW,
    counting only failures after the last successful login (a success resets the
    counter). The lock lasts until the oldest of those failures leaves the window.
    """
    threshold = settings.LOGIN_LOCKOUT_THRESHOLD
    window = settings.LOGIN_LOCKOUT_WINDOW

    # Ordered by id (insertion order), not by time: unambiguous even when two attempts
    # share a timestamp.
    last_success_id = (
        LoginAttempt.objects.filter(user=user, succeeded=True).order_by("-id").values("id")[:1]
    )
    recent_failures = list(
        LoginAttempt.objects.filter(
            user=user,
            succeeded=False,
            attempted_at__gt=now - window,
            id__gt=Coalesce(Subquery(last_success_id), Value(0)),
        )
        .order_by("-id")
        .values_list("attempted_at", flat=True)[:threshold]
    )

    if len(recent_failures) < threshold:
        return None
    return recent_failures[-1] + window - now


def session_summary(user: User) -> SessionSummary:
    # [0] is the current login, [1] the one before it.
    previous = list(
        LoginAttempt.objects.filter(user=user, succeeded=True)
        .order_by("-id")
        .values_list("attempted_at", flat=True)[1:2]
    )
    customer = Customer.objects.filter(user=user).first()

    return SessionSummary(
        email=user.email,
        first_name=customer.first_name if customer else None,
        last_name=customer.last_name if customer else None,
        previous_login_at=previous[0] if previous else None,
    )
