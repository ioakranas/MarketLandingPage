"""OpenAPI building blocks: the Problem Details shapes and their documented responses.

Every error response of the API is application/problem+json (see common.api); these
helpers describe that once, so each endpoint only lists which problems it can return.
"""

from drf_spectacular.authentication import SessionScheme
from drf_spectacular.utils import OpenApiExample, OpenApiResponse
from rest_framework import serializers

from common.api import PROBLEM_BASE_URL, PROBLEM_CONTENT_TYPE
from common.authentication import CSRF_FAILED_DETAIL


class SessionAuthenticationScheme(SessionScheme):
    """Documents our SessionAuthentication subclass as cookie authentication.

    (Registered by being defined: drf-spectacular collects extension subclasses.)
    """

    target_class = "common.authentication.SessionAuthentication"


class ProblemSerializer(serializers.Serializer):
    """RFC 9457 Problem Details."""

    type = serializers.URLField(help_text="Stable identifier of the problem: clients branch on this.")
    title = serializers.CharField(help_text="Short, human-readable summary of the problem type.")
    status = serializers.IntegerField(help_text="The HTTP status code.")
    detail = serializers.CharField(help_text="Explanation of this occurrence, safe to show to users.")


class ValidationProblemSerializer(ProblemSerializer):
    errors = serializers.DictField(
        child=serializers.CharField(),
        help_text="One message per invalid field, ready to show next to that field.",
    )


def problem(
    status: int,
    problem_type: str,
    title: str,
    detail: str,
    description: str,
    *,
    errors: dict[str, str] | None = None,
) -> tuple[tuple[int, str], OpenApiResponse]:
    """A documented problem response, keyed by (status, media type) for extend_schema."""
    example = {"type": PROBLEM_BASE_URL + problem_type, "title": title, "status": status, "detail": detail}
    if errors is not None:
        example["errors"] = errors
    response = OpenApiResponse(
        response=ValidationProblemSerializer if errors is not None else ProblemSerializer,
        description=description,
        examples=[OpenApiExample(problem_type, value=example)],
    )
    return (status, PROBLEM_CONTENT_TYPE), response


def validation_problem(errors: dict[str, str]):
    return problem(
        400,
        "validation-error",
        "Validation failed",
        "One or more fields are invalid.",
        "Invalid input. Every invalid field is reported, one message each.",
        errors=errors,
    )


CSRF_PROBLEM = problem(
    403,
    "csrf-failed",
    "Forbidden",
    CSRF_FAILED_DETAIL,
    "Missing or wrong CSRF token: send the csrftoken cookie's value in the X-CSRFToken header.",
)

RATE_LIMITED_PROBLEM = problem(
    429,
    "rate-limited",
    "Too many requests",
    "Too many requests. Please try again in 1 minute(s).",
    "Too many requests from this IP address; the Retry-After header says when to try "
    "again (seconds).",
)


def either(*problems, description: str):
    """Several problem types sharing one status code, documented as one response."""
    (key, first), *_ = problems
    examples = [example for _, response in problems for example in response.examples]
    return key, OpenApiResponse(response=first.response, description=description, examples=examples)


NOT_AUTHENTICATED_PROBLEM = problem(
    401,
    "not-authenticated",
    "Unauthorized",
    "Authentication credentials were not provided.",
    "No valid session: log in with POST /api/v1/sessions.",
)
