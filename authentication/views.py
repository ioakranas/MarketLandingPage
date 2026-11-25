"""The login and welcome pages. GET only: logging in and out go through the session API
(POST /api/v1/sessions, DELETE /api/v1/sessions/current), called by the page's JavaScript.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_safe

from authentication.selectors import session_summary
from common.decorators import anonymous_only
from common.validation import client_config


@require_safe
@anonymous_only
@ensure_csrf_cookie
def login_page(request: HttpRequest) -> HttpResponse:
    return render(request, "login.html", {"validation_config": client_config()})


@require_safe
# Without a session: plain redirect to /login (no ?next=, so no open-redirect surface).
@login_required(redirect_field_name=None)
# Personal data: never stored by the browser or a proxy, so after logout the Back
# button can't show it again.
@never_cache
@ensure_csrf_cookie  # for the logout request
def welcome_page(request: HttpRequest) -> HttpResponse:
    return render(request, "welcome.html", {"summary": session_summary(request.user)})
