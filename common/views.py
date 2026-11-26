"""Project-wide error views: API clients get Problem Details, browsers get HTML pages.

Every response under /api/ is application/problem+json, including the errors that
happen outside the API views themselves: unknown URLs (404), CSRF rejections by
Django's middleware (403) and unexpected server errors (500).
"""

import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views import defaults
from django.views.csrf import csrf_failure as html_csrf_failure

from common.api import PROBLEM_BASE_URL, PROBLEM_CONTENT_TYPE
from common.audit import audit
from common.authentication import CSRF_FAILED_DETAIL
from common.http import client_ip
from common.logs import request_id_var


def _is_api(request: HttpRequest) -> bool:
    return request.path.startswith("/api/")


def _problem(status: int, problem: str, title: str, detail: str) -> JsonResponse:
    return JsonResponse(
        {"type": PROBLEM_BASE_URL + problem, "title": title, "status": status, "detail": detail},
        status=status,
        content_type=PROBLEM_CONTENT_TYPE,
    )


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """settings.CSRF_FAILURE_VIEW."""
    # Django's reason is a fixed technical phrase ("CSRF cookie not set."), no user data.
    audit("csrf.failed", level=logging.WARNING, path=request.path, reason=reason, ip=client_ip(request))
    if _is_api(request):
        return _problem(403, "csrf-failed", "Forbidden", CSRF_FAILED_DETAIL)
    return html_csrf_failure(request, reason)


def page_not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    """handler404 (config.urls)."""
    if _is_api(request):
        return _problem(404, "not-found", "Not Found", "No API resource at this URL.")
    return defaults.page_not_found(request, exception)


def server_error(request: HttpRequest) -> HttpResponse:
    """handler500 (config.urls). Django has already logged the traceback (logger
    django.request) with this request's id, which the client gets as a reference for
    support; nothing about the error itself is revealed."""
    if _is_api(request):
        reference = request_id_var.get() or "-"
        return _problem(
            500,
            "internal-error",
            "Internal Server Error",
            f"An unexpected error occurred. Please try again later. Reference: {reference}",
        )
    return defaults.server_error(request)
