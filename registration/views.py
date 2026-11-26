"""The sign-up page. GET only: the form is submitted by JavaScript to the JSON API
(POST /api/v1/registrations), so the browser and any other client share one backend.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_safe

from common.decorators import anonymous_only
from common.validation import client_config
from countries.selectors import list_countries


@require_safe
@anonymous_only
@ensure_csrf_cookie  # the page's JavaScript sends this token in the X-CSRFToken header
def register_page(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "register.html",
        {
            # Rendered into the page (no extra request on load); same data as /api/v1/countries.
            "countries": list_countries(),
            "validation_config": client_config(),
        },
    )
