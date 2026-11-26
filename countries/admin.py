from django.contrib import admin

from countries.models import Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "iso_code", "dial_code")
    search_fields = ("name", "iso_code")
