"""Client IP resolution, shared by rate limiting and the login audit."""

import pytest
from django.test import RequestFactory
from rest_framework.settings import api_settings

from common.http import client_ip


def request(**meta):
    return RequestFactory().get("/", **meta)


def test_connection_address_by_default():
    assert client_ip(request(REMOTE_ADDR="203.0.113.7", HTTP_X_FORWARDED_FOR="1.2.3.4")) == "203.0.113.7"


def test_forwarded_address_behind_a_trusted_proxy(monkeypatch):
    monkeypatch.setattr(api_settings, "NUM_PROXIES", 1)
    forwarded = request(REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="spoofed, 198.51.100.4")
    assert client_ip(forwarded) == "198.51.100.4"  # the entry our proxy added


@pytest.mark.parametrize("value", ["not-an-ip", ""])
def test_invalid_address_is_none(value):
    assert client_ip(request(REMOTE_ADDR=value)) is None
