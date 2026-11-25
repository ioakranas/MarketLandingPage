"""The login and welcome pages."""

import pytest

from authentication.models import LoginAttempt
from tests.authentication.conftest import NOW

pytestmark = pytest.mark.django_db


# --- login page ---------------------------------------------------------------------


def test_login_page_renders_the_form_for_the_api(client):
    response = client.get("/login")
    html = response.content.decode()

    assert response.status_code == 200
    assert 'data-api="/api/v1/sessions"' in html
    assert 'data-success-url="/welcome"' in html
    assert 'autocomplete="current-password"' in html
    assert 'href="/register"' in html
    assert response.cookies["csrftoken"].value


def test_logged_in_visitors_skip_the_login_page(client, customer):
    client.force_login(customer.user)
    assert client.get("/login")["Location"] == "/welcome"


def test_login_page_is_read_only(client):
    assert client.post("/login").status_code == 405


# --- welcome page -------------------------------------------------------------------


def test_welcome_requires_login(client):
    response = client.get("/welcome")
    assert response.status_code == 302
    assert response["Location"] == "/login"  # no ?next=: nothing to redirect to elsewhere


def test_first_login_welcome(client, customer):
    client.force_login(customer.user)
    html = client.get("/welcome").content.decode()

    assert "Welcome back, Ioannis!" in html
    assert "You are logged in as <strong>ioannis@example.com</strong>." in html
    assert "This is your first login." in html
    assert 'data-logout="/api/v1/sessions/current"' in html


def test_welcome_shows_the_previous_login(client, customer):
    LoginAttempt.objects.create(user=customer.user, succeeded=True, attempted_at=NOW)
    LoginAttempt.objects.create(user=customer.user, succeeded=True)  # the current login
    client.force_login(customer.user)

    html = client.get("/welcome").content.decode()
    assert "Your previous login was on 24 November 2026, 12:00 UTC." in html


def test_welcome_escapes_customer_data(client, make_customer):
    """Names are rendered with Django's auto-escaping (no stored XSS)."""
    customer = make_customer()
    customer.first_name = "<script>x</script>"  # bypasses validation on purpose
    customer.save(update_fields=["first_name"])
    client.force_login(customer.user)

    html = client.get("/welcome").content.decode()
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html


def test_welcome_for_staff_without_customer_profile(client, make_user):
    client.force_login(make_user("staff@example.com"))
    assert "Welcome back!" in client.get("/welcome").content.decode()


def test_welcome_is_never_cached(client, customer):
    """After logout, the Back button must not show the personal page from a cache."""
    client.force_login(customer.user)
    cache_control = client.get("/welcome")["Cache-Control"]
    assert "no-store" in cache_control
    assert "private" in cache_control


# --- error pages --------------------------------------------------------------------


def test_unknown_page_uses_the_site_layout(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "Page not found" in response.content.decode()
