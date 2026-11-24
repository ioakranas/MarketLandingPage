"""Page structure: assets, accessibility hooks and header navigation."""

import re

import pytest


def test_stylesheet_is_served(client):
    response = client.get("/static/css/main.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"


def test_logo_is_served(client):
    assert client.get("/static/img/hfm-logo.svg").status_code == 200


@pytest.mark.parametrize("path", ["/register", "/login"])
def test_page_is_responsive_and_styled(client, path):
    html = client.get(path).get_data(as_text=True)
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "/static/css/main.css" in html


@pytest.mark.parametrize(
    ("path", "inputs"),
    [
        ("/register", ["first_name", "last_name", "country", "phone_code", "phone", "email", "password"]),
        ("/login", ["email", "password"]),
    ],
)
def test_every_input_has_a_label(client, path, inputs):
    html = client.get(path).get_data(as_text=True)
    for name in inputs:
        assert f'<label class="visually-hidden" for="{name}">' in html
        assert f'id="{name}"' in html


def test_error_is_linked_to_its_input(client):
    html = client.post("/register", data={"first_name": "Ana"}).get_data(as_text=True)

    field = re.search(r'<input[^>]*id="first_name"[^>]*>', html).group(0)
    assert 'aria-invalid="true"' in field
    assert 'aria-describedby="first_name-error"' in field
    assert '<p class="field__error" id="first_name-error">' in html


def test_valid_fields_are_not_marked_invalid(client):
    html = client.post("/register", data={"first_name": "Ioannis"}).get_data(as_text=True)

    field = re.search(r'<input[^>]*id="first_name"[^>]*>', html).group(0)
    assert "aria-invalid" not in field


def test_plus_sign_is_decorative_only(client):
    html = client.get("/register").get_data(as_text=True)
    assert '<span class="phone__plus" aria-hidden="true">+</span>' in html


def test_register_page_links_to_login_and_vice_versa(client):
    assert 'href="/login">Login</a>' in client.get("/register").get_data(as_text=True)
    assert 'href="/register">Register</a>' in client.get("/login").get_data(as_text=True)
