from django.contrib import admin

from authentication.models import LoginAttempt


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
