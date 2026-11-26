import pytest

pytestmark = pytest.mark.django_db


def test_lists_countries_with_dial_codes(api_client):
    response = api_client.get("/api/v1/countries")

    assert response.status_code == 200
    assert response.json() == [
        {"iso_code": "CY", "name": "Cyprus", "dial_code": "357"},
        {"iso_code": "GR", "name": "Greece", "dial_code": "30"},
        {"iso_code": "GB", "name": "United Kingdom", "dial_code": "44"},
    ]


def test_is_read_only(api_client):
    response = api_client.post("/api/v1/countries", {"iso_code": "FR"}, format="json")
    assert response.status_code == 405
