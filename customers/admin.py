from django.contrib import admin

from customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "user", "country", "phone", "created_at")
    list_filter = ("country",)
    search_fields = ("first_name", "last_name", "user__email", "phone")
    list_select_related = ("user", "country")
    readonly_fields = ("created_at",)
