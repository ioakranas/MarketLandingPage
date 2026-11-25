"""Root URL configuration."""

import os

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from authentication.api import CurrentSessionView, SessionCreateView
from authentication.views import login_page, welcome_page
from countries.api import CountryListView
from registration.api import RegistrationView
from registration.views import register_page

# Back office. The path is configurable so production can move it off the
# well-known /admin/ that bots probe.
ADMIN_PATH = os.environ.get("DJANGO_ADMIN_PATH", "admin/")

# Versioned in the URL: a breaking change becomes /api/v2/ while v1 keeps working.
api_v1 = [
    path("countries", CountryListView.as_view(), name="countries"),
    path("registrations", RegistrationView.as_view(), name="registrations"),
    path("sessions", SessionCreateView.as_view(), name="sessions"),
    path("sessions/current", CurrentSessionView.as_view(), name="current-session"),
]

# Pages: GET only. Their JavaScript talks to the API above.
pages = [
    path("", RedirectView.as_view(pattern_name="register"), name="home"),
    path("register", register_page, name="register"),
    path("login", login_page, name="login"),
    path("welcome", welcome_page, name="welcome"),
]

urlpatterns = [
    *pages,
    path("api/v1/", include((api_v1, "v1"))),
    path(ADMIN_PATH, admin.site.urls),
]
