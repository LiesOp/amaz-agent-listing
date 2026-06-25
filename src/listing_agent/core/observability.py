from time import perf_counter
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from listing_agent.core.logging import get_logger, reset_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"
logger = get_logger("listing_agent.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit structured request and error logs with a stable request ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid4().hex}"
        token = set_request_id(request_id)
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((perf_counter() - started) * 1000)
            logger.exception(
                "request_error method=%s path=%s duration_ms=%s",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        else:
            duration_ms = int((perf_counter() - started) * 1000)
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "request_completed method=%s path=%s status_code=%s duration_ms=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            reset_request_id(token)
