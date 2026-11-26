"""Request context: a request id for correlation, and one access log line per request
(static files excepted)."""

import logging
import re
import time
import uuid

from django.conf import settings

from common.logs import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
# A proxy or client may send its own id (end-to-end tracing). Accepted only if it looks
# like an id: nothing else from outside gets into the logs this way.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")

access_logger = logging.getLogger("access")


class RequestContextMiddleware:
    """First in the middleware chain, so it covers every request and response."""

    def __init__(self, get_response):
        self.get_response = get_response
        # CSS, JS, fonts and icons: a dozen requests per page that say nothing about
        # users or security, so they get no access line (their errors are still logged).
        self.static_prefix = "/" + settings.STATIC_URL.lstrip("/")

    def __call__(self, request):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            # Django turns exceptions into responses inside get_response, so there is
            # always a response here (500s included).
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id  # quoted by users to support
            if request.path.startswith(self.static_prefix):
                return response
            access_logger.info(
                "%s %s %s",
                request.method,
                request.path,
                response.status_code,
                extra={
                    "method": request.method,
                    # Path only: query strings can carry personal data or tokens.
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            return response
        finally:
            request_id_var.reset(token)
