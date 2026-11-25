"""Project-wide views."""

import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.csrf import csrf_failure as html_csrf_failure

from common.api import PROBLEM_BASE_URL, PROBLEM_CONTENT_TYPE
from common.audit import audit
from common.authentication import CSRF_FAILED_DETAIL
from common.http import client_ip


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """settings.CSRF_FAILURE_VIEW: API clients get Problem Details, pages get Django's page.

    Keeps the promise of a single error format for every API response.
    """
    # Django's reason is a fixed technical phrase ("CSRF cookie not set."), no user data.
    audit("csrf.failed", level=logging.WARNING, path=request.path, reason=reason, ip=client_ip(request))
    if request.path.startswith("/api/"):
        return JsonResponse(
            {
                "type": PROBLEM_BASE_URL + "csrf-failed",
                "title": "Forbidden",
                "status": 403,
                "detail": CSRF_FAILED_DETAIL,
            },
            status=403,
            content_type=PROBLEM_CONTENT_TYPE,
        )
    return html_csrf_failure(request, reason)
