"""Root URL configuration."""

import os

from django.contrib import admin
from django.urls import include, path

from countries.api import CountryListView
from registration.api import RegistrationView

# Back office. The path is configurable so production can move it off the
# well-known /admin/ that bots probe.
ADMIN_PATH = os.environ.get("DJANGO_ADMIN_PATH", "admin/")

# Versioned in the URL: a breaking change becomes /api/v2/ while v1 keeps working.
api_v1 = [
    path("countries", CountryListView.as_view(), name="countries"),
    path("registrations", RegistrationView.as_view(), name="registrations"),
]

urlpatterns = [
    path("api/v1/", include((api_v1, "v1"))),
    path(ADMIN_PATH, admin.site.urls),
]
