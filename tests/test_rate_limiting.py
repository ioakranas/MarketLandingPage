"""Per-IP rate limits on the anonymous, abusable endpoints (sign-up and login)."""

import pytest
from django.conf import settings

from accounts.models import User

pytestmark = pytest.mark.django_db

RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]


def limit(scope: str) -> int:
    return int(RATES[scope].split("/")[0])  # "10/hour" -> 10


def register(client, number: int, **extra):
    return client.post(
        "/api/v1/registrations",
        {
            "first_name": "Ioannis",
            "last_name": "Papadopoulos",
            "country": "GR",
            "phone_code": "30",
            "phone": "6912345678",
            "email": f"user{number}@example.com",
            "password": "Secret#123",
            "terms": True,
        },
        format="json",
        **extra,
    )


def log_in(client, **extra):
    return client.post(
        "/api/v1/sessions",
        {"email": "ioannis@example.com", "password": "Wrong#123"},
        format="json",
        **extra,
    )


def test_registrations_are_limited_per_ip(api_client):
    for number in range(limit("registrations")):
        assert register(api_client, number).status_code == 201

    response = register(api_client, 999)

    assert response.status_code == 429
    assert response["Content-Type"] == "application/problem+json"
    assert response.json()["type"].endswith("/rate-limited")
    assert int(response["Retry-After"]) > 0
    assert not User.objects.filter(email="user999@example.com").exists()  # never processed


def test_login_is_limited_per_ip_across_accounts(api_client, make_customer):
    """Credential stuffing: one IP trying many accounts, each below its own lockout."""
    make_customer()
    for _ in range(limit("login")):
        assert log_in(api_client).status_code in {401, 429}  # 429 = account lockout

    response = log_in(api_client)

    assert response.status_code == 429
    assert response.json()["type"].endswith("/rate-limited")


def test_another_ip_has_its_own_limit(api_client):
    for number in range(limit("registrations")):
        register(api_client, number)

    assert register(api_client, 998, REMOTE_ADDR="203.0.113.9").status_code == 201


def test_fake_x_forwarded_for_does_not_reset_the_limit(api_client):
    """Without a trusted proxy the header is the client's word, so it is ignored."""
    for number in range(limit("registrations")):
        register(api_client, number, HTTP_X_FORWARDED_FOR=f"198.51.100.{number}")

    response = register(api_client, 999, HTTP_X_FORWARDED_FOR="198.51.100.250")
    assert response.status_code == 429


def test_trusted_proxy_count_uses_the_forwarded_client_address(api_client, monkeypatch):
    """Behind one proxy, the proxy's last X-Forwarded-For entry is the real client."""
    from rest_framework.settings import api_settings

    monkeypatch.setattr(api_settings, "NUM_PROXIES", 1)
    for number in range(limit("registrations")):
        register(api_client, number, HTTP_X_FORWARDED_FOR="198.51.100.1")

    assert register(api_client, 998, HTTP_X_FORWARDED_FOR="198.51.100.1").status_code == 429
    assert register(api_client, 999, HTTP_X_FORWARDED_FOR="198.51.100.2").status_code == 201


def test_reading_endpoints_are_not_limited(api_client):
    for _ in range(limit("login") * 2):
        assert api_client.get("/api/v1/countries").status_code == 200
