"""Request helpers."""

import ipaddress

from rest_framework.throttling import BaseThrottle


def client_ip(request) -> str | None:
    """The client's IP address, resolved exactly as rate limiting does.

    Uses REMOTE_ADDR, or X-Forwarded-For only behind the number of trusted proxies set in
    settings.REST_FRAMEWORK["NUM_PROXIES"]. Anything that isn't a valid IP gives None.
    """
    candidate = BaseThrottle().get_ident(request)
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None
