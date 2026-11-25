"""Django settings (comparable to Spring Boot's application.yml).

Secure by default: everything environment-specific or sensitive comes from environment
variables, and the defaults are the safe choice (DEBUG off, secure headers on).
"""

import os
from datetime import timedelta
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
    "drf_spectacular",
    # Project apps, one per feature
    "common",
    "accounts",
    "countries",
    "customers",
    "registration",
    "authentication",
]

# Identity model with email login, defined before the first migration (Django's advice:
# swapping the user model later is very hard).
AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    # First: the request id and access log cover everything below, errors included.
    "common.middleware.RequestContextMiddleware",
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
    "DEFAULT_AUTHENTICATION_CLASSES": ["common.authentication.SessionAuthentication"],
    # Secure by default: endpoints must opt in to anonymous access.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Every error as RFC 9457 Problem Details.
    "EXCEPTION_HANDLER": "common.api.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
    # Rate limiting per client IP for the endpoints that set a throttle_scope (the
    # anonymous, expensive or abusable ones). Counters live in the cache (see CACHES).
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        # Sign-up: generous for people (and shared office IPs), useless for bots.
        "registrations": "10/hour",
        # Login: per IP, across all accounts (credential stuffing). The per-account
        # lockout (LOGIN_LOCKOUT_*) covers guessing one account's password.
        "login": "10/minute",
    },
    # How the client IP is found. 0 = no proxy: use the connection's address and IGNORE
    # X-Forwarded-For, which the client controls (otherwise a fake header per request
    # would get a fresh limit every time). Behind N trusted proxies (load balancer,
    # CDN), set DJANGO_NUM_PROXIES=N.
    "NUM_PROXIES": int(os.environ.get("DJANGO_NUM_PROXIES", "0")),
    # OpenAPI 3 schema generated from the views and serializers (drf-spectacular).
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# Served at /api/v1/schema (OpenAPI 3) and /api/v1/docs (Swagger UI).
SWAGGER_UI_VERSION = "5.17.14"  # pinned: the UI is loaded from a CDN
SPECTACULAR_SETTINGS = {
    "TITLE": "HF Markets Landing Page API",
    "VERSION": "1.0.0",
    "DESCRIPTION": (
        "Customer registration and login.\n\n"
        "**Authentication**: server-side session. `POST /api/v1/sessions` sets an HttpOnly "
        "`sessionid` cookie; the browser sends it automatically.\n\n"
        "**CSRF**: every POST and DELETE must send the value of the `csrftoken` cookie in "
        "the `X-CSRFToken` header (this page does it for you).\n\n"
        "**Errors**: always `application/problem+json` (RFC 9457). Branch on `type`; show "
        "`detail` to users; `errors` holds one message per invalid field.\n\n"
        "**Versioning**: in the path. Breaking changes get a new version; v1 keeps working."
    ),
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
    "SERVE_INCLUDE_SCHEMA": False,  # the schema endpoint doesn't document itself
    # Separate request/response components: write-only fields (password) never
    # appear in a response schema.
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Registration", "description": "Customer sign-up."},
        {"name": "Sessions", "description": "Log in, current session, log out."},
        {"name": "Countries", "description": "Reference data for the sign-up form."},
    ],
    "SWAGGER_UI_DIST": f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}",
    "SWAGGER_UI_FAVICON_HREF": (
        f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/favicon-32x32.png"
    ),
    "SWAGGER_UI_SETTINGS": {"displayOperationId": True},
}

# --- passwords ----------------------------------------------------------------------

# Argon2id first: new passwords are hashed with it, and hashes made with any other
# hasher in the list (or with outdated Argon2 parameters) are upgraded on next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# Applied to every password: registration API, admin, createsuperuser, password changes.
AUTH_PASSWORD_VALIDATORS = [
    # Our policy: length, capital letter, number, symbol (same rules the forms show).
    {"NAME": "common.passwords.PasswordPolicyValidator"},
    # Blocklist of ~20,000 common passwords ("Password1!" passes the policy, not this).
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    # Not too close to the email address.
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ["email"]},
    },
]

# --- logging ------------------------------------------------------------------------

# One line per event on stdout (12-factor: the platform collects and ships it).
# json: for log platforms (production default). text: readable, for a developer's
# terminal (default when DEBUG is on). Every line carries the request id.
LOG_FORMAT = os.environ.get("DJANGO_LOG_FORMAT") or ("text" if DEBUG else "json")
LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "common.logs.JsonFormatter"},
        "text": {"()": "common.logs.TextFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": LOG_FORMAT,
        },
        # Silences a logger properly (a logger without any handler falls back to
        # Python's "last resort" output for warnings).
        "null": {"class": "logging.NullHandler"},
    },
    # Everything (our code, Django, libraries) goes through the root logger's handler.
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # Django's defaults would print some lines twice and email errors to ADMINS.
        "django": {"handlers": [], "level": LOG_LEVEL, "propagate": True},
        # 4xx responses are in our access log already; keep only server errors (5xx,
        # with traceback) from Django's request logger.
        "django.request": {"level": "ERROR"},
        # CSRF rejections are audit events (csrf.failed) with the same details.
        "django.security.csrf": {"level": "ERROR"},
        # runserver's own access lines: replaced by ours (logger "access").
        "django.server": {"handlers": ["null"], "propagate": False},
    },
}

# --- cache --------------------------------------------------------------------------

# Holds the rate-limit counters. In-process memory: fine for one server process. With
# several processes or servers the counters must be shared: Redis in production.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# --- login --------------------------------------------------------------------------

# Where @login_required sends visitors without a session.
LOGIN_URL = "login"

# An account locks after this many failed logins within the window (failures before
# the last successful login don't count). Brute force on one account becomes ~20
# guesses per hour; per-IP rate limiting covers guessing across many accounts.
LOGIN_LOCKOUT_THRESHOLD = 5
LOGIN_LOCKOUT_WINDOW = timedelta(minutes=15)

# --- sessions & cookies -------------------------------------------------------------

# Server-side sessions (database): logging out really invalidates the session.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
# Idle timeout, as expected from a financial app: logged out after 30 minutes without
# activity (Django's default is 2 weeks). Saving on every request makes the expiry
# sliding: each request pushes it 30 minutes ahead, at the cost of one session write.
SESSION_COOKIE_AGE = 30 * 60
SESSION_SAVE_EVERY_REQUEST = True
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
