"""API-wide error handling: every error response is RFC 9457 Problem Details.

One format for all failures (validation, conflicts, wrong method, malformed JSON, ...)
means clients need a single error-handling path. Comparable to a Spring
@ControllerAdvice returning ProblemDetail.

    {
      "type": "https://hfmarkets.example/problems/validation-error",
      "title": "Validation failed",
      "status": 400,
      "detail": "One or more fields are invalid.",
      "errors": {"email": "Please enter a valid email address (e.g. name@example.com)."}
    }
"""

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

PROBLEM_CONTENT_TYPE = "application/problem+json"
PROBLEM_BASE_URL = "https://hfmarkets.example/problems/"


class ApiProblem(exceptions.APIException):
    """Domain error with a stable problem type, raised by API views."""

    def __init__(self, status_code: int, problem: str, title: str, detail: str, **extra):
        super().__init__(detail)
        self.status_code = status_code
        self.problem = problem
        self.title = title
        self.extra = extra


def problem_response(status_code: int, problem: str, title: str, detail: str, **extra) -> Response:
    body = {
        "type": PROBLEM_BASE_URL + problem,
        "title": title,
        "status": status_code,
        "detail": detail,
        **extra,
    }
    return Response(body, status=status_code, content_type=PROBLEM_CONTENT_TYPE)


def api_exception_handler(exc, context):
    """DRF's EXCEPTION_HANDLER: map every exception to Problem Details."""
    if isinstance(exc, ApiProblem):
        return problem_response(exc.status_code, exc.problem, exc.title, str(exc.detail), **exc.extra)

    if isinstance(exc, exceptions.ValidationError):
        return problem_response(
            status.HTTP_400_BAD_REQUEST,
            "validation-error",
            "Validation failed",
            "One or more fields are invalid.",
            errors=_field_errors(exc.detail),
        )

    # Let DRF build its response first (status code, headers such as Allow or
    # Retry-After), then replace the body.
    response = exception_handler(exc, context)
    if response is None:
        return None  # unexpected error: Django returns a 500 (and logs it)
    problem = exc.default_code.replace("_", "-")  # e.g. method_not_allowed -> method-not-allowed
    problem_body = problem_response(response.status_code, problem, response.status_text, str(exc.detail))
    for header, value in response.headers.items():
        if header.lower() not in {"content-type", "content-length"}:
            problem_body[header] = value
    return problem_body


def _field_errors(detail) -> dict[str, str]:
    """DRF error lists -> one message per field: {"email": "..."}.

    Errors that aren't tied to a field (e.g. a JSON array instead of an object) are
    reported under "non_field_errors".
    """
    if isinstance(detail, dict):
        return {field: _first_message(messages) for field, messages in detail.items()}
    return {"non_field_errors": _first_message(detail)}


def _first_message(messages) -> str:
    while isinstance(messages, (list, tuple)) and messages:
        messages = messages[0]
    return str(messages)
