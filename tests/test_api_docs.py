"""The OpenAPI document and Swagger UI: the published contract of the API."""

import pytest
from django.conf import settings
from django.core.management import call_command

pytestmark = pytest.mark.django_db

PROBLEM_TYPE = "application/problem+json"


@pytest.fixture(scope="module")
def schema(django_db_blocker):
    from rest_framework.test import APIClient

    with django_db_blocker.unblock():
        response = APIClient().get("/api/v1/schema", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert response.status_code == 200
    return response.json()


def test_schema_is_valid_openapi_without_warnings(tmp_path):
    """Quality gate: an undocumented or ambiguous endpoint fails the build."""
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(tmp_path / "schema.yml"))


def test_every_endpoint_is_documented_with_a_stable_operation_id(schema):
    operations = {
        (path, method): operation["operationId"]
        for path, methods in schema["paths"].items()
        for method, operation in methods.items()
    }
    assert operations == {
        ("/api/v1/countries", "get"): "listCountries",
        ("/api/v1/registrations", "post"): "registerCustomer",
        ("/api/v1/sessions", "post"): "createSession",
        ("/api/v1/sessions/current", "get"): "getCurrentSession",
        ("/api/v1/sessions/current", "delete"): "deleteCurrentSession",
    }


@pytest.mark.parametrize(
    ("path", "method", "statuses"),
    [
        ("/api/v1/registrations", "post", {"400", "403", "409"}),
        ("/api/v1/sessions", "post", {"400", "401", "403", "429"}),
        ("/api/v1/sessions/current", "get", {"401"}),
        ("/api/v1/sessions/current", "delete", {"401", "403"}),
    ],
)
def test_errors_are_documented_as_problem_details(schema, path, method, statuses):
    responses = schema["paths"][path][method]["responses"]
    errors = {status for status in responses if status.startswith(("4", "5"))}

    assert errors == statuses
    for status in statuses:
        assert list(responses[status]["content"]) == [PROBLEM_TYPE]


def test_password_is_write_only_and_absent_from_responses(schema):
    components = schema["components"]["schemas"]

    assert components["RegistrationRequest"]["properties"]["password"]["writeOnly"] is True
    assert components["LoginRequest"]["properties"]["password"]["writeOnly"] is True
    assert "password" not in components["CustomerResponse"]["properties"]
    assert "password" not in components["SessionResponse"]["properties"]


def test_session_cookie_is_the_documented_authentication(schema):
    assert schema["components"]["securitySchemes"]["cookieAuth"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "sessionid",
    }
    # Anonymous endpoints say so; the current session requires the cookie.
    assert schema["paths"]["/api/v1/registrations"]["post"]["security"] == [{}]
    assert schema["paths"]["/api/v1/countries"]["get"]["security"] == [{}]
    assert schema["paths"]["/api/v1/sessions/current"]["get"]["security"] == [{"cookieAuth": []}]


def test_swagger_ui_is_served_with_a_pinned_version(client):
    response = client.get("/api/v1/docs")
    html = response.content.decode()

    assert response.status_code == 200
    assert f"swagger-ui-dist@{settings.SWAGGER_UI_VERSION}" in html
    assert "@latest" not in html
