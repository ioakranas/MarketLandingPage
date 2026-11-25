"""Django settings (comparable to Spring Boot's application.yml).

Secure by default: everything environment-specific or sensitive comes from environment
variables, and the defaults are the safe choice (DEBUG off, secure headers on).
"""

import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent


def env_flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").lower() in {"1", "true", "yes"}


# --- core ---------------------------------------------------------------------------

# Required in production. Without it a random per-process key is used: safe, but
# sessions do not survive a restart.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or get_random_secret_key()

DEBUG = env_flag("DJANGO_DEBUG")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # Project apps, one per feature
    "common",
    "accounts",
    "countries",
    "customers",
    "registration",
]

# Identity model with email login, defined before the first migration (Django's advice:
# swapping the user model later is very hard).
AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves static files efficiently in any environment (no separate web server needed).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- database -----------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DATABASE_PATH", BASE_DIR / "hfmarkets.sqlite3"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- REST API -----------------------------------------------------------------------

REST_FRAMEWORK = {
    # JSON in, JSON out. (No HTML "browsable API": Swagger UI documents the API.)
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # Our own pages call the API with the session cookie.
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    # Secure by default: endpoints must opt in to anonymous access.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Every error as RFC 9457 Problem Details.
    "EXCEPTION_HANDLER": "common.api.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
}

# --- passwords ----------------------------------------------------------------------

# Argon2id first: new passwords are hashed with it, and hashes made with any other
# hasher in the list (or with outdated Argon2 parameters) are upgraded on next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# --- sessions & cookies -------------------------------------------------------------

# Server-side sessions (database): logging out really invalidates the session.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "common.views.csrf_failure"
# Must be on whenever the site is served over HTTPS (always, in production).
SESSION_COOKIE_SECURE = env_flag("DJANGO_SECURE_COOKIES")
CSRF_COOKIE_SECURE = env_flag("DJANGO_SECURE_COOKIES")

# --- security headers ---------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- i18n / time --------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- static files -------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Filled by `manage.py collectstatic` at deployment (then served compressed and cached).
STATIC_ROOT = BASE_DIR / "staticfiles"
# Until collected (local runs, tests), WhiteNoise serves straight from STATICFILES_DIRS.
WHITENOISE_USE_FINDERS = True
