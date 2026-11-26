"""Error responses outside the API views: Problem Details under /api/, HTML elsewhere."""

import logging

import pytest
from django.test import Client
from django.urls import path

from config.urls import urlpatterns as project_urls

pytestmark = pytest.mark.django_db

PROBLEM_TYPE = "application/problem+json"


def broken_view(request):
    raise RuntimeError("database password is hunter2")  # must never reach the client


# The project's URLs plus two views that fail, one API-like and one page-like.
urlpatterns = [
    path("api/v1/broken", broken_view),
    path("broken", broken_view),
    *project_urls,
]
handler404 = "common.views.page_not_found"
handler500 = "common.views.server_error"


def test_unknown_api_url_is_a_problem_details_404(client):
    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response["Content-Type"] == PROBLEM_TYPE
    assert response.json() == {
        "type": "https://hfmarkets.example/problems/not-found",
        "title": "Not Found",
        "status": 404,
        "detail": "No API resource at this URL.",
    }


def test_unknown_page_stays_html(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response["Content-Type"].startswith("text/html")


@pytest.mark.urls(__name__)
def test_api_server_error_is_problem_details_with_a_reference(caplog):
    client = Client(raise_request_exception=False)

    with caplog.at_level(logging.ERROR):
        response = client.get("/api/v1/broken")

    assert response.status_code == 500
    assert response["Content-Type"] == PROBLEM_TYPE
    body = response.json()
    reference = response["X-Request-ID"]
    assert body["type"].endswith("/internal-error")
    assert body["detail"] == (
        f"An unexpected error occurred. Please try again later. Reference: {reference}"
    )
    assert "hunter2" not in response.content.decode()  # nothing internal leaks
    # ...but the traceback is in the logs, findable by the same reference.
    [error] = [record for record in caplog.records if record.name == "django.request"]
    assert error.request_id == reference
    assert error.exc_info and "hunter2" in str(error.exc_info[1])


@pytest.mark.urls(__name__)
def test_page_server_error_stays_html():
    response = Client(raise_request_exception=False).get("/broken")

    assert response.status_code == 500
    assert response["Content-Type"].startswith("text/html")
    assert "Something went wrong" in response.content.decode()
