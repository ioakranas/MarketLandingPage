"""API authentication.

Kept apart from common.api on purpose: DRF imports the authentication classes while
rest_framework.views is still loading, so this module must not import DRF views.
"""

import logging

from rest_framework import authentication, exceptions

from common.audit import audit

# HTTP requires a WWW-Authenticate challenge on every 401. There is no registered
# scheme for cookie sessions, so we name ours: it tells the client "log in via
# POST /api/v1/sessions" (fetch() never shows a browser login dialog for it).
SESSION_AUTH_CHALLENGE = 'Session realm="api"'

CSRF_FAILED_DETAIL = "CSRF verification failed. Reload the page and try again."


class CsrfFailed(exceptions.PermissionDenied):
    default_detail = CSRF_FAILED_DETAIL
    default_code = "csrf_failed"  # -> problem type .../csrf-failed


class SessionAuthentication(authentication.SessionAuthentication):
    """DRF's session authentication, answering 401 (not 403) to anonymous requests.

    DRF only sends 401 when the scheme provides a WWW-Authenticate challenge; otherwise
    it downgrades to 403. 401 = "who are you?", 403 = "I know you, and no".
    """

    def authenticate_header(self, request) -> str:
        return SESSION_AUTH_CHALLENGE

    def enforce_csrf(self, request) -> None:
        # For logged-in requests DRF checks CSRF here, not in Django's middleware.
        # Same problem type as the middleware's failure view (common.views).
        try:
            super().enforce_csrf(request)
        except exceptions.PermissionDenied as error:
            from common.http import client_ip  # here: this module must not import DRF views

            audit(
                "csrf.failed",
                level=logging.WARNING,
                path=request.path,
                reason=str(error.detail),
                ip=client_ip(request),
            )
            raise CsrfFailed from None
