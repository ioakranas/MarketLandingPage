# HF Markets – Registration & Login

A registration and login landing page following the provided Figma design, built with
**Python (Django + Django REST Framework)** and **SQLite**.

The pages are server-rendered HTML whose JavaScript talks to a **versioned JSON API**
(`/api/v1/...`, documented with OpenAPI/Swagger). Validation rules live in one place on
the server and are shared with the browser. The project is covered by **348 automated
tests (100% line and branch coverage)**.

- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Running the tests](#running-the-tests)
- [Assignment requirements: where and how](#assignment-requirements-where-and-how)
- [Architecture](#architecture)
- [The API](#the-api)
- [Security](#security)
- [Beyond the brief, and deliberate deviations](#beyond-the-brief-and-deliberate-deviations)
- [Trade-offs and known limits](#trade-offs-and-known-limits)
- [Production and deployment](#production-and-deployment)
- [Development](#development)

---

## Requirements

| | Requirement | Notes |
|---|---|---|
| **Python** | **3.12 or newer** | Developed and tested on 3.15.2. Django 6 needs 3.12+. |
| **SQLite** | Nothing to install | Built into Python. Django 6 needs SQLite ≥ 3.37: the python.org installers for Windows and macOS include a newer one; on Linux, Python uses the system's (check with `python -c "import sqlite3; print(sqlite3.sqlite_version)"`). |
| **OS** | Windows, macOS or Linux | Commands below are given for PowerShell and bash. |
| **Browser** | A current Chrome, Edge, Firefox or Safari | |
| **Internet** | For `pip install`; at runtime for Google Fonts and the Swagger UI files (CDN) | The app works offline, with fallback fonts. |

Not needed: Node.js, Docker, a database server or a build step.

Python packages (exact versions in [`requirements.txt`](requirements.txt)): Django 6.1,
Django REST Framework 3.18, drf-spectacular 0.30 (OpenAPI), argon2-cffi 25.1 (password
hashing), WhiteNoise 6 (static files); pytest, pytest-django and pytest-cov for the tests.

## Quick start

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

If PowerShell refuses to run `Activate.ps1` ("running scripts is disabled"), allow local
scripts once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or skip activation
and use `.venv\Scripts\python manage.py ...` instead.

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

`migrate` creates the SQLite database (`hfmarkets.sqlite3`) and seeds the three sample
countries (Greece, Cyprus, United Kingdom). Then open <http://127.0.0.1:8000>.

| URL | What |
|---|---|
| <http://127.0.0.1:8000/register> | Sign-up form (the start page) |
| <http://127.0.0.1:8000/login> | Login |
| <http://127.0.0.1:8000/welcome> | Welcome page after login |
| <http://127.0.0.1:8000/api/v1/docs> | **Swagger UI**: the API, with "Try it out" |
| <http://127.0.0.1:8000/api/v1/schema> | The OpenAPI 3 document |
| <http://127.0.0.1:8000/admin/> | Back office (create an account with `python manage.py createsuperuser`) |

**Things to try:** submit the empty form (every field explains what is wrong); pick a
country and watch the dial code fill in; register, then register the same email again
with different capitals; log in with a wrong password five times (the account locks
for 15 minutes); log in correctly and log out. The terminal shows one log line per
request plus an `audit` line for each security event.

## Running the tests

```bash
pytest                                   # all 348 tests (about 6 seconds)
pytest --cov --cov-report=term-missing   # with the coverage report
pytest tests/authentication -v           # one area
pytest -k lockout                        # by name

# The OpenAPI document must validate without a single warning (also run by the tests)
python manage.py spectacular --validate --fail-on-warn --file schema.yml
```

## Assignment requirements: where and how

| Requirement | Implementation | Proven by |
|---|---|---|
| Server-side validation (Python) | `common/validation.py`, enforced by the API serializers | `tests/common/test_validation.py` (94 tests), `tests/registration/test_api.py` |
| SQLite with proper validation and security | Database `CHECK` constraints, case-insensitive unique email, Argon2id password hashes, parameterised SQL (ORM) | `tests/customers/`, `tests/accounts/`, `tests/test_project.py` (schema checks) |
| First and last name: length > 3 | Taken literally: four characters or more, on both sides and in the database | `test_validation.py`, `test_invalid_field_returns_problem_details` |
| Country code numeric | Digits only, and it must match the selected country | same |
| Email format | One pattern, compiled by both Python and JavaScript | same, plus `tests/authentication/test_api.py` |
| Password: 1 capital, 1 number, 1 symbol | Plus a minimum length, a common-password blocklist and a similarity check (see below) | `test_validation.py`, `tests/common/test_passwords.py` |
| Clear, specific message per failure | One message per field, all invalid fields reported at once, identical in browser and API | `test_all_invalid_fields_reported_at_once` |
| Thank-you message after sign-up | "Thank you for signing up, *First name*!" replaces the form | `tests/registration/test_views.py` |
| Login: email format and clear errors | Same email rule; field errors, then "Invalid email or password." | `tests/authentication/test_api.py` |
| Country selection fills the phone code (3 countries) | Countries and dial codes come from the database; `static/js/main.js` fills the code | `test_countries_come_from_the_database_with_their_dial_codes` |
| Front-end validation with the same rules | The server renders its rules and messages as JSON; `main.js` applies them live | `test_validation_rules_are_embedded_as_json` |
| Responsive, all screen resolutions | Mobile-first CSS with two breakpoints | Checked in a real browser from 320 px to 2560 px wide, without horizontal overflow |

The front end was also exercised end to end in a real browser (Microsoft Edge driven by
Playwright, kept outside the repository): live errors, dial-code autofill, the 409, 401
and lockout messages, keyboard focus, mobile layout, and the Content-Security-Policy
(no violations on the pages, the admin or Swagger).

## Architecture

### Apps: one per feature

```
config/          settings, URLs, WSGI entry point
common/          shared building blocks: validation rules, API error format, logging,
                 audit events, authentication class, custom database lookups
accounts/        identity: who can log in (email, password hash, staff flags)
customers/       the customer profile (names, country, phone), one-to-one with a user
countries/       reference data (seeded by a data migration) and GET /api/v1/countries
registration/    the sign-up use case: API, service, page
authentication/  login, lockout, login history, logout: API, service, pages
templates/  static/   pages, CSS and JavaScript
tests/           mirrors the apps
```

Dependencies point one way: `registration` and `authentication` (use cases) use
`accounts`, `customers` and `countries`; those never import the use cases. `accounts`
depends on nothing.

**Identity is separate from the profile.** `accounts.User` holds only what logging in
needs, so back-office staff and customers share one authentication mechanism without
staff needing customer fields. `customers.Customer` holds the personal data.

### Layers inside an app

| Module | Role |
|---|---|
| `api.py` | JSON endpoints (DRF `APIView`s) |
| `serializers.py` | Request and response shapes |
| `services.py` | Use cases that write, in transactions |
| `selectors.py` | Read-only queries |
| `models.py` | Entities and their database constraints |
| `views.py` | GET-only HTML pages |

### API-first pages

The pages are plain server-rendered HTML with **no form handling of their own**. Their
JavaScript sends JSON to the API and displays its answers: field errors under the
fields, other errors above the form. The browser is simply the first client of the same
API that a mobile app or a partner would use.

```
Browser ──GET /register──────────────▶ registration.views   (HTML + validation rules as JSON)
Browser ──POST /api/v1/registrations─▶ registration.api ─▶ registration.services ─▶ SQLite
        ◀──201 customer | 400/409 Problem Details──
```

### One set of validation rules

`common/validation.py` defines every limit, label and message once. The API applies
them, the page receives them as JSON (`client_config()`, embedded with Django's escaping
`json_script`) and `main.js` applies them live, and the models derive their database
constraints from the same limits. A rule changes in one place, and the browser, the
API, the admin and the database all follow.

Validation therefore happens in three layers: the browser (convenience), the server (the
authority), the database (the last line of defence, for any code path).

### Design patterns in use

| Pattern | Where |
|---|---|
| Service layer + selectors (reads separated from writes) | `services.py` / `selectors.py` |
| Active Record (Django ORM) | Models load and save themselves |
| DTO | DRF serializers |
| Value objects | Frozen dataclasses: `Registration`, `LoginCredentials`, `SessionSummary` |
| Facade + unit of work | `register_customer()`: one transaction across three apps, with a savepoint |
| Exception translation | `common/api.py` maps every exception to Problem Details |
| Strategy, chosen in settings | Password hashers, password validators, authentication and throttle classes, log formatters |
| Chain of responsibility | The middleware chain |
| Decorator | `login_required`, `csrf_protect`, `never_cache`, `anonymous_only` |
| Template method | `common/authentication.py` overrides DRF's `authenticate_header` and `enforce_csrf` hooks |
| Adapter | `PasswordPolicyValidator` adapts our rules to Django's validator interface; the admin login form adapts the login service |
| Observer | Django signals (`login()` updates `last_login`) |
| Null object | `NullHandler` for silenced loggers, `AnonymousUser` |
| Context object | The request id in a `ContextVar`, on every log line |

There is no dependency-injection container, which is idiomatic for Python: wiring goes
through settings (dotted paths) and plain function arguments, and tests replace
collaborators directly (for example the clock used by the lockout).

## The API

| Method and path | Purpose | Responses |
|---|---|---|
| `GET /api/v1/countries` | Countries available at sign-up | 200 |
| `POST /api/v1/registrations` | Register a customer | 201, 400, 403, 409, 429 |
| `POST /api/v1/sessions` | Log in | 201, 400, 401, 403, 429 |
| `GET /api/v1/sessions/current` | The current session | 200, 401 |
| `DELETE /api/v1/sessions/current` | Log out | 204, 401, 403 |

- **Versioned in the path**: a breaking change becomes `/api/v2/`, and v1 keeps working.
- **JSON only**, in and out (a form-encoded body gets 415).
- **Every error is [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457)**
  (`application/problem+json`), including 404s, CSRF failures and unexpected 500s:

  ```json
  {
    "type": "https://hfmarkets.example/problems/validation-error",
    "title": "Validation failed",
    "status": 400,
    "detail": "One or more fields are invalid.",
    "errors": {"email": "Please enter a valid email address (e.g. name@example.com)."}
  }
  ```

  Clients branch on `type`, show `detail` to users and `errors` next to the fields. A 500
  carries the request id as a reference for support, and nothing internal.
- **Login is creating a session resource**, and logout is deleting it.
- **No internal ids in responses**: the client always acts as "me", and sequential keys
  would reveal how many customers exist. A public identifier would be a random UUID.
- The **OpenAPI document is generated from the code** (drf-spectacular), with stable
  `operationId`s for client generators, and is validated by the test suite.

## Security

**Passwords**

- Argon2id (the current OWASP recommendation). Hashes made with older settings or
  algorithms are upgraded automatically at the next login.
- One policy for every account, customers and staff: length, capital, number and symbol,
  plus Django's blocklist of about 20,000 common passwords and a check against similarity
  to the email. It applies to the API, the admin and `createsuperuser` alike.
- Passwords are never trimmed, never returned, never logged.

**Login**

- **Account lockout**: 5 failures within 15 minutes lock the account for the rest of the
  window (429 with `Retry-After`). While locked, passwords are not even checked. A
  successful login resets the count.
- **Per-IP rate limiting**: 10 login attempts per minute and 10 sign-ups per hour, against
  credential stuffing across many accounts and bulk sign-ups.
- The same answer for an unknown email and a wrong password, which also take the same
  time (a password hash is computed either way).
- **The admin login goes through the same service**, so staff logins get the same
  lockout, records and audit events.
- Every attempt on an existing account is recorded (`authentication_login_attempt`).
  Attempts for unknown emails are logged with the address masked, never stored. A purge
  command enforces retention: `python manage.py purge_login_attempts --days 30`.

**Sessions**

- Server-side sessions in the database: logging out deletes the session, so a copied
  cookie stops working at once.
- A new session id and CSRF token at login (session fixation protection).
- HttpOnly, SameSite=Lax cookies; Secure cookies in production.
- Logged out after 30 minutes without activity.
- The welcome page is never cached, so the Back button can't show it after logout.

**Requests and the browser**

- CSRF protection on every state-changing request, including the anonymous sign-up and
  login (prevents "login CSRF").
- A strict **Content-Security-Policy**: scripts only from our own origin, no inline
  scripts at all. The page JavaScript inserts user data as text, never as HTML.
- Framing forbidden (clickjacking), `nosniff`, a same-origin referrer policy.
- HTTPS redirect, HSTS and Secure cookies with one switch in production (`DJANGO_HTTPS=1`).
- The client IP ignores `X-Forwarded-For` unless trusted proxies are configured, so a
  forged header can't bypass the rate limit or falsify the audit log.

**Data**

- Database constraints repeat the validation rules: no code path can store invalid data.
  The admin applies the same rules and messages as sign-up.
- Duplicate emails are detected by the unique constraint, not by a prior query, so two
  simultaneous sign-ups can't both succeed. Hashing happens before the insert, so the
  "already registered" answer takes as long as a successful sign-up.
- Names in Latin characters only (see the deviations below).

**Logging**

- Structured logs (JSON in production), every line tagged with its request id, which is
  also returned in the `X-Request-ID` header.
- Security audit events on their own logger: registration, login success and failure
  with the reason, lockout, logout, rate limiting, CSRF failures.
- No personal data: no passwords, tokens, session ids, names or phone numbers, and emails
  only masked (`io***@example.com`). A test formats every log record exactly as it would
  be shipped and checks this.

## Beyond the brief, and deliberate deviations

The brief asks for a form with validation; the role is about how production systems are
built. Everything below goes beyond the brief on purpose, and each item is optional to
read.

**Additions:** the versioned JSON API and its OpenAPI documentation; account lockout and
rate limiting; the login and welcome pages with logout and the previous-login time
("not you? contact support"); structured logging and audit events; the back office
(Django admin) with the same validation; production settings (HTTPS, CSP, fail-fast
configuration).

**Rules stricter than the brief, and why:**

| Rule | Why |
|---|---|
| Names in Latin letters only (accents allowed: é, ñ, ß) | Names must match identity documents for KYC/AML (the passport's machine-readable zone is Latin-only); payment networks (SEPA/SWIFT) restrict character sets; and it prevents look-alike spoofing (Cyrillic "а" vs Latin "a"). |
| Names may contain spaces, hyphens and apostrophes, and must start and end with a letter | "Anne-Marie", "O'Neil", "van der Berg"; but not "--" or "123". |
| Phone: 6–14 digits, spaces and dashes ignored | A plausible national number (without the dial code) for any country; exact per-country lengths are a production item (see trade-offs). |
| Password: 8–128 characters, not a common password, not similar to the email | The brief's three character classes alone accept "Password1!", one of the most common passwords. 128 bounds the hashing cost of a single request. |
| Privacy Policy and Terms must be accepted | As in the design; enforced by the server, not only by the checkbox. |

## Trade-offs and known limits

- **"Length > 3" is applied literally.** Real names such as "Li" or "Ana" are rejected. I
  kept the brief's rule and flag it here: in production I'd ask the business to lower it.
- **The pages need JavaScript.** Forms are sent by `fetch` to the API (API-first), so
  there is no fallback without JavaScript, only a notice. The API itself works with any
  client.
- **Account existence can be inferred** from "email already registered" (409) and from the
  lockout message. Both are deliberate for usability and mitigated by rate limiting and
  equal timing. The full fix is an email-verification flow: always answer "check your
  inbox", and tell an existing owner by email instead.
- **No email verification yet**, so an address is not proven to belong to the person.
- **The phone number isn't validated per country.** National lengths differ, and E.164
  caps the full international number at 15 digits, which 6–14 digits plus a 3-digit dial
  code can exceed. A library such as `phonenumbers` would validate it exactly in production.
- **Acceptance of the terms is implied by the account's creation time.** With versioned
  terms in production, an append-only `terms_acceptances` table (customer, version, time,
  IP) would record each acceptance.
- **Rate-limit counters live in process memory**, correct for a single server process.
  With several processes or servers they must be shared (Redis).
- **The lockout check and the attempt record aren't atomic**: parallel guesses can slightly
  exceed five. The per-IP rate limit bounds this; PostgreSQL row locks would close it.
- **SQLite** allows one writer at a time: fine here, not for production traffic.
- **Google Fonts and the Swagger UI files come from CDNs**, so visitors' IPs reach third
  parties (GDPR). In production they'd be self-hosted.
- **Visual design**: the layout follows the Figma design; the logo is a lightweight
  wordmark and the background photo is a CSS gradient in its colours.
- **Tests**: the JavaScript was verified in a real browser but isn't part of the pytest
  suite; the PostgreSQL variant of one custom lookup isn't exercised (tests run on SQLite).

## Production and deployment

`python manage.py runserver` is Django's development server. In production the
application runs under a WSGI server behind a TLS-terminating proxy:

```
Internet → load balancer / nginx (TLS) → gunicorn (several workers) → Django (config.wsgi) → PostgreSQL, Redis
```

```bash
python manage.py collectstatic --noinput        # static files for WhiteNoise
python manage.py migrate
python manage.py check --deploy                 # passes with DJANGO_HTTPS=1 and a secret key
gunicorn config.wsgi:application --workers 4
```

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_HTTPS` | off | **Production mode**: Secure cookies, HTTP→HTTPS redirect, HSTS; requires `DJANGO_SECRET_KEY` |
| `DJANGO_SECRET_KEY` | random per process | Signs sessions and CSRF tokens. Required in production: startup fails without it rather than giving each worker its own key |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated host names |
| `DJANGO_DEBUG` | off | Django's debug pages (development only) |
| `DJANGO_NUM_PROXIES` | `0` | Trusted proxies in front of the app: decides whether `X-Forwarded-For` and `X-Forwarded-Proto` are trusted |
| `DJANGO_HSTS_SECONDS` | one year | HSTS duration when `DJANGO_HTTPS` is on |
| `DJANGO_DATABASE_PATH` | `hfmarkets.sqlite3` | Location of the SQLite file |
| `DJANGO_ADMIN_PATH` | `admin/` | Moves the back office off the path bots probe (keep the trailing `/`) |
| `DJANGO_LOG_FORMAT` | `json` (`text` with `DJANGO_DEBUG`) | Log line format |
| `DJANGO_LOG_LEVEL` | `INFO` | Log level |

The security limits (lockout threshold and window, rate limits) are policy, so they are
in `config/settings.py` and change through reviewed commits rather than environment
variables.

### What production would add

- **PostgreSQL** instead of SQLite, the application in its own schema with a
  least-privilege database role; **Redis** for sessions and rate-limit counters.
- **Authentication**: for a single first-party web app, server-side sessions are the right
  choice (instant revocation, no token exposed to JavaScript). At company scale: an
  identity provider (OpenID Connect) handling login, MFA and lockout centrally; a
  backend-for-frontend for the web, so tokens never reach the browser; Authorization Code
  with PKCE for mobile apps; short-lived JWTs only between services. **MFA**, with step-up
  authentication for withdrawals and changes of bank details.
- **Email verification** and a CAPTCHA or proof-of-work after repeated sign-ups.
- **Edge protection** (WAF, API gateway) for limits that can change instantly during an
  attack; the admin behind a VPN or an IP allow-list.
- **Logs shipped to a SIEM**, with alerts on lockouts and rate limits, and a defined
  retention period (client IPs are personal data under GDPR).
- Self-hosted fonts and Swagger UI (`drf-spectacular-sidecar`), and the API documentation
  visible to staff only.

## Development

### Debugging in VS Code

[`.vscode/launch.json`](.vscode/launch.json) has two configurations (Python extension
required, with the `.venv` interpreter selected): **"Django: runserver"** (breakpoints in
views, services and selectors; press F5) and **"pytest: all tests"**.

### Logs

With `DJANGO_DEBUG=1` the logs are readable text; otherwise one JSON object per line.
`DJANGO_LOG_FORMAT=text` forces text.

```text
INFO access [9007eb61...] GET /register 200 method=GET path=/register status=200 duration_ms=23.8
WARNING audit [40883317...] login.failed event=login.failed reason=wrong_password user_id=1 ip=127.0.0.1
```

### The database

The database is the single file `hfmarkets.sqlite3`. Any SQLite client can open it (for
example DBeaver, or the "SQLite Viewer" extension in VS Code). Main tables:
`accounts_user`, `customers_customer`, `countries_country`,
`authentication_login_attempt` and `django_session`. Use a read-only connection while
the server runs: SQLite locks the whole file during a write.

Unlocking an account while testing: wait 15 minutes, or

```bash
python manage.py shell -c "from authentication.models import LoginAttempt; LoginAttempt.objects.filter(succeeded=False).delete()"
```

### Dependencies

`pyproject.toml` declares the compatible version ranges; `requirements.txt` pins the exact
versions the tests pass with. After changing `pyproject.toml`, regenerate the pins in a
fresh virtual environment: `pip install ".[dev]"`, then `pip freeze`.

### History

The commit history tells how the project was built:
<https://github.com/ioakranas/MarketLandingPage>. A first version in Flask is kept under
the tag `v1-flask`; the project then moved to Django, the framework HFM uses, keeping the
validation rules, front end and test scenarios.
