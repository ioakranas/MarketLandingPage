"""HTTP layer (the @Controller package): one blueprint per area of responsibility.

- registration: onboarding of new customers
- auth:         authentication (login / logout) and the login_required guard
- account:      pages for logged-in customers
"""

from collections.abc import Mapping


def form_without_password(form: Mapping[str, str]) -> dict[str, str]:
    """Submitted values to re-display after an error. Passwords never go back to the browser."""
    return {key: value for key, value in form.items() if key != "password"}
