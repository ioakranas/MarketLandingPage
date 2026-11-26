"""The sign-up page (GET only; the form is sent to the API by JavaScript)."""

import json
import re

import pytest

from common.validation import client_config

pytestmark = pytest.mark.django_db


def test_home_redirects_to_register(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/register"


def test_register_page_renders_the_form_for_the_api(client):
    response = client.get("/register")
    html = response.content.decode()

    assert response.status_code == 200
    assert 'data-api="/api/v1/registrations"' in html
    for name in ["first_name", "last_name", "country", "phone_code", "phone", "email", "password", "terms"]:
        assert f'name="{name}"' in html
    assert 'href="/login"' in html


def test_countries_come_from_the_database_with_their_dial_codes(client):
    html = client.get("/register").content.decode()

    options = re.findall(r'<option value="(\w+)" data-dial-code="(\d+)">([^<]+)</option>', html)
    assert options == [("CY", "357", "Cyprus"), ("GR", "30", "Greece"), ("GB", "44", "United Kingdom")]


def test_validation_rules_are_embedded_as_json(client):
    html = client.get("/register").content.decode()

    raw = re.search(r'<script id="validation-config" type="application/json">(.*?)</script>', html, re.S)
    assert json.loads(raw.group(1)) == client_config()


def test_page_sets_the_csrf_cookie_for_the_javascript(client):
    response = client.get("/register")
    assert response.cookies["csrftoken"].value
    assert not response.cookies["csrftoken"]["httponly"]  # main.js must be able to read it


def test_success_message_is_a_template_filled_as_text(client):
    html = client.get("/register").content.decode()
    assert '<template id="register-success">' in html
    assert 'data-field="first_name"' in html
    assert '<h2 class="card__title" tabindex="-1">' in html  # focus target after sign-up


def test_logged_in_visitors_go_to_their_welcome_page(client, make_customer):
    client.force_login(make_customer().user)
    response = client.get("/register")
    assert response.status_code == 302
    assert response["Location"] == "/welcome"


def test_page_is_read_only(client):
    assert client.post("/register").status_code == 405
