"""Project-wide views."""

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.csrf import csrf_failure as html_csrf_failure

from common.api import PROBLEM_BASE_URL, PROBLEM_CONTENT_TYPE


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """settings.CSRF_FAILURE_VIEW: API clients get Problem Details, pages get Django's page.

    Keeps the promise of a single error format for every API response.
    """
    if request.path.startswith("/api/"):
        return JsonResponse(
            {
                "type": PROBLEM_BASE_URL + "csrf-failed",
                "title": "Forbidden",
                "status": 403,
                "detail": "CSRF verification failed. Reload the page and try again.",
            },
            status=403,
            content_type=PROBLEM_CONTENT_TYPE,
        )
    return html_csrf_failure(request, reason)
