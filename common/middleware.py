"""Request context: a request id for correlation, and one access log line per request."""

import logging
import re
import time
import uuid

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
