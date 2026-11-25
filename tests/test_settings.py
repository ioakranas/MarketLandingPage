"""Project configuration: secure defaults and a clean system check."""

import importlib

import pytest
from django.conf import settings
from django.core.management import call_command


def load_settings(monkeypatch, **env):
    for name in ["DJANGO_SECRET_KEY", "DJANGO_DEBUG", "DJANGO_SECURE_COOKIES"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    import config.settings

    return importlib.reload(config.settings)


def test_debug_is_off_by_default(monkeypatch):
    assert load_settings(monkeypatch).DEBUG is False


def test_debug_can_be_enabled_for_development(monkeypatch):
    assert load_settings(monkeypatch, DJANGO_DEBUG="1").DEBUG is True


def test_secret_key_comes_from_environment(monkeypatch):
    assert load_settings(monkeypatch, DJANGO_SECRET_KEY="from-env").SECRET_KEY == "from-env"


def test_random_secret_key_when_environment_missing(monkeypatch):
    first = load_settings(monkeypatch).SECRET_KEY
    second = load_settings(monkeypatch).SECRET_KEY
    assert first != second
    assert len(first) >= 50


def test_secure_cookies_switch(monkeypatch):
    secure = load_settings(monkeypatch, DJANGO_SECURE_COOKIES="1")
    assert secure.SESSION_COOKIE_SECURE is True
    assert secure.CSRF_COOKIE_SECURE is True


def test_argon2_is_the_default_password_hasher():
    assert settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")


def test_cookie_and_header_hardening():
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
    assert settings.X_FRAME_OPTIONS == "DENY"
    assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True


@pytest.mark.django_db
def test_system_check_passes():
    call_command("check")
