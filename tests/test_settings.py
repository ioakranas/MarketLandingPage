"""Project configuration: secure defaults and a clean system check."""

import importlib

import pytest
from django.conf import settings
from django.core.management import call_command


def load_settings(monkeypatch, **env):
    for name in ["DJANGO_SECRET_KEY", "DJANGO_DEBUG", "DJANGO_HTTPS", "DJANGO_HSTS_SECONDS",
                 "DJANGO_NUM_PROXIES", "DJANGO_ALLOWED_HOSTS", "DJANGO_LOG_FORMAT",
                 "DJANGO_LOG_LEVEL"]:
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


def test_local_mode_has_no_https_requirements(monkeypatch):
    local = load_settings(monkeypatch)
    assert local.SESSION_COOKIE_SECURE is False
    assert local.SECURE_SSL_REDIRECT is False
    assert local.SECURE_HSTS_SECONDS == 0


def test_https_mode_turns_on_everything_that_belongs_together(monkeypatch):
    production = load_settings(monkeypatch, DJANGO_HTTPS="1", DJANGO_SECRET_KEY="from-env")
    assert production.SESSION_COOKIE_SECURE is True
    assert production.CSRF_COOKIE_SECURE is True
    assert production.SECURE_SSL_REDIRECT is True
    assert production.SECURE_HSTS_SECONDS == 31536000  # one year
    assert not hasattr(production, "SECURE_PROXY_SSL_HEADER")  # no proxy: nothing trusted


def test_hsts_duration_is_configurable(monkeypatch):
    short = load_settings(monkeypatch, DJANGO_HTTPS="1", DJANGO_SECRET_KEY="k", DJANGO_HSTS_SECONDS="3600")
    assert short.SECURE_HSTS_SECONDS == 3600


def test_https_behind_a_proxy_trusts_its_forwarded_proto(monkeypatch):
    behind_proxy = load_settings(
        monkeypatch, DJANGO_HTTPS="1", DJANGO_SECRET_KEY="k", DJANGO_NUM_PROXIES="1"
    )
    assert behind_proxy.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_production_refuses_to_start_without_a_secret_key(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        load_settings(monkeypatch, DJANGO_HTTPS="1")


def test_allowed_hosts_tolerate_spaces(monkeypatch):
    hosts = load_settings(monkeypatch, DJANGO_ALLOWED_HOSTS=" example.com , www.example.com ,")
    assert hosts.ALLOWED_HOSTS == ["example.com", "www.example.com"]


def test_argon2_is_the_default_password_hasher(monkeypatch):
    # Read from the settings module: tests swap in a fast hasher at runtime.
    hashers = load_settings(monkeypatch).PASSWORD_HASHERS
    assert hashers[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"


def test_client_ip_ignores_x_forwarded_for_by_default(monkeypatch):
    assert load_settings(monkeypatch).REST_FRAMEWORK["NUM_PROXIES"] == 0


def test_trusted_proxy_count_comes_from_environment(monkeypatch):
    assert load_settings(monkeypatch, DJANGO_NUM_PROXIES="2").REST_FRAMEWORK["NUM_PROXIES"] == 2


def test_logs_are_json_in_production_and_text_while_debugging(monkeypatch):
    production = load_settings(monkeypatch)
    assert production.LOGGING["handlers"]["console"]["formatter"] == "json"
    assert production.LOGGING["root"]["level"] == "INFO"
    assert load_settings(monkeypatch, DJANGO_DEBUG="1").LOGGING["handlers"]["console"]["formatter"] == "text"


def test_log_format_and_level_from_environment(monkeypatch):
    custom = load_settings(monkeypatch, DJANGO_LOG_FORMAT="text", DJANGO_LOG_LEVEL="warning")
    assert custom.LOGGING["handlers"]["console"]["formatter"] == "text"
    assert custom.LOGGING["root"]["level"] == "WARNING"


def test_api_is_json_only_and_secure_by_default():
    api = settings.REST_FRAMEWORK
    assert api["DEFAULT_RENDERER_CLASSES"] == ["rest_framework.renderers.JSONRenderer"]
    assert api["DEFAULT_PERMISSION_CLASSES"] == ["rest_framework.permissions.IsAuthenticated"]
    assert api["EXCEPTION_HANDLER"] == "common.api.api_exception_handler"


def test_content_security_policy_is_strict():
    from django.utils.csp import CSP

    assert settings.SECURE_CSP["script-src"] == [CSP.SELF]
    assert settings.SECURE_CSP["default-src"] == [CSP.SELF]
    assert CSP.UNSAFE_INLINE not in settings.SECURE_CSP["style-src"]


def test_cookie_and_header_hardening():
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
    assert settings.SESSION_COOKIE_AGE == 30 * 60
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.X_FRAME_OPTIONS == "DENY"
    assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True


@pytest.mark.django_db
def test_system_check_passes():
    call_command("check")
