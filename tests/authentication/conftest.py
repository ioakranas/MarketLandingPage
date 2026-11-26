from datetime import UTC, datetime, timedelta

import pytest

from authentication import services

NOW = datetime(2026, 11, 24, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch):
    """Controllable 'now' for the authentication services."""

    class Clock:
        now = NOW

        def advance(self, **delta):
            self.now += timedelta(**delta)

    clock = Clock()
    monkeypatch.setattr(services, "_now", lambda: clock.now)
    return clock


@pytest.fixture
def customer(make_customer):
    return make_customer()  # ioannis@example.com / tests.conftest.PASSWORD
