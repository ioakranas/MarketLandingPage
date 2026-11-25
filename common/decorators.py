"""View decorators shared by the page views."""

from django.contrib.auth.decorators import user_passes_test


def anonymous_only(view):
    """Pages for visitors (register, login): logged-in users go to their welcome page."""
    return user_passes_test(
        lambda user: not user.is_authenticated, login_url="welcome", redirect_field_name=None
    )(view)
