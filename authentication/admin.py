from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError

from authentication.models import LoginAttempt
from authentication.services import AccountLocked, InvalidCredentials, authenticate_customer
from common.http import client_ip
from common.validation import LoginCredentials


class LockoutAdminAuthenticationForm(AdminAuthenticationForm):
    """The admin's login form, through the same login service as the API.

    Django's own form calls authenticate() directly, which would leave the most
    privileged login without lockout, attempt records or audit events. Going through
    authenticate_customer() gives every login path the same protection.
    """

    def clean(self):
        email = (self.cleaned_data.get("username") or "").strip()
        password = self.cleaned_data.get("password")
        if email and password:
            credentials = LoginCredentials(email, password)
            try:
                self.user_cache = authenticate_customer(credentials, client_ip(self.request))
            except AccountLocked as locked:
                raise ValidationError(
                    "Too many failed login attempts. "
                    f"Please try again in {locked.minutes_remaining} minute(s).",
                    code="account_locked",
                ) from None
            except InvalidCredentials:
                raise self.get_invalid_login_error() from None
            self.confirm_login_allowed(self.user_cache)  # staff only
        return self.cleaned_data


admin.site.login_form = LockoutAdminAuthenticationForm


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Read-only audit trail for support ("why is my account locked?")."""

    list_display = ("attempted_at", "user", "succeeded", "ip_address")
    list_filter = ("succeeded",)
    search_fields = ("user__email", "ip_address")
    list_select_related = ("user",)
    date_hierarchy = "attempted_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
