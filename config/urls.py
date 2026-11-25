"""Root URL configuration: each app contributes its own routes."""

import os

from django.contrib import admin
from django.urls import path

# Back office. The path is configurable so production can move it off the
# well-known /admin/ that bots probe.
ADMIN_PATH = os.environ.get("DJANGO_ADMIN_PATH", "admin/")

urlpatterns = [
    path(ADMIN_PATH, admin.site.urls),
]
