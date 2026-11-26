"""Root URL configuration."""

import os

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.utils.csp import CSP
from django.views.decorators.csp import csp_override
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerSplitView

from authentication.api import CurrentSessionView, SessionCreateView
from authentication.views import login_page, welcome_page
from countries.api import CountryListView
from registration.api import RegistrationView
from registration.views import register_page

# Back office. The path is configurable so production can move it off the
# well-known /admin/ that bots probe.
ADMIN_PATH = os.environ.get("DJANGO_ADMIN_PATH", "admin/")

# Swagger UI comes from a CDN (pinned version) and ships one small inline <style>; its
# own script is served as a separate file (the "split" view) so no inline script is
# needed. This page alone gets that wider policy.
SWAGGER_CDN = "https://cdn.jsdelivr.net"
swagger_ui = csp_override(
    {
        **settings.SECURE_CSP,
        "script-src": [CSP.SELF, SWAGGER_CDN],
        "style-src": [CSP.SELF, SWAGGER_CDN, CSP.UNSAFE_INLINE],
        "img-src": [CSP.SELF, SWAGGER_CDN, "data:"],
    }
)(SpectacularSwaggerSplitView.as_view(url_name="v1:schema"))

# Versioned in the URL: a breaking change becomes /api/v2/ while v1 keeps working.
api_v1 = [
    path("countries", CountryListView.as_view(), name="countries"),
    path("registrations", RegistrationView.as_view(), name="registrations"),
    path("sessions", SessionCreateView.as_view(), name="sessions"),
    path("sessions/current", CurrentSessionView.as_view(), name="current-session"),
    # API documentation: the OpenAPI 3 document and Swagger UI on top of it.
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", swagger_ui, name="docs"),
]

# Pages: GET only. Their JavaScript talks to the API above.
pages = [
    path("", RedirectView.as_view(pattern_name="register"), name="home"),
    path("register", register_page, name="register"),
    path("login", login_page, name="login"),
    path("welcome", welcome_page, name="welcome"),
]

# Error pages: Problem Details under /api/, the site's HTML pages elsewhere.
handler404 = "common.views.page_not_found"
handler500 = "common.views.server_error"

urlpatterns = [
    *pages,
    path("api/v1/", include((api_v1, "v1"))),
    path(ADMIN_PATH, admin.site.urls),
]
