"""The Problem Details exception handler, unit-level, and the API CSRF failure view."""

import pytest
from rest_framework import exceptions
from rest_framework.test import APIClient

from common.api import api_exception_handler

pytestmark = pytest.mark.django_db


def test_unexpected_errors_are_left_to_django():
    # None -> Django's 500 handling (and logging); internals never leak into the body.
    assert api_exception_handler(ValueError("boom"), {}) is None


def test_validation_error_without_fields():
    response = api_exception_handler(exceptions.ValidationError("Something is off."), {})

    assert response.status_code == 400
    assert response.data["errors"] == {"non_field_errors": "Something is off."}


def test_nested_field_errors_keep_the_first_message():
    error = exceptions.ValidationError({"email": [["first", "second"]]})
    assert api_exception_handler(error, {}).data["errors"] == {"email": "first"}


def test_drf_headers_are_preserved():
    response = api_exception_handler(exceptions.MethodNotAllowed("PUT"), {})

    assert response.status_code == 405
    assert response.data["type"].endswith("/method-not-allowed")


def test_throttled_is_a_rate_limited_problem_with_retry_after():
    response = api_exception_handler(exceptions.Throttled(wait=61), {})

    assert response.status_code == 429
    assert response["Retry-After"] == "61"
    assert response.data == {
        "type": "https://hfmarkets.example/problems/rate-limited",
        "title": "Too many requests",
        "status": 429,
        "detail": "Too many requests. Please try again in 2 minute(s).",
    }


def test_throttled_without_wait_has_no_retry_after():
    response = api_exception_handler(exceptions.Throttled(), {})

    assert response.status_code == 429
    assert "Retry-After" not in response
    assert response.data["detail"] == "Too many requests. Please try again in 1 minute(s)."


def test_api_csrf_failure_is_problem_details():
    response = APIClient(enforce_csrf_checks=True).post(
        "/api/v1/registrations", {}, format="json"
    )

    assert response.status_code == 403
    assert response["Content-Type"] == "application/problem+json"
    assert response.json()["type"].endswith("/csrf-failed")


def test_page_csrf_failure_stays_html(client):
    from django.test import Client

    response = Client(enforce_csrf_checks=True).post("/admin/login/", {})

    assert response.status_code == 403
    assert response["Content-Type"].startswith("text/html")
