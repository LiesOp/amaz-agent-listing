import logging
import sys
from contextvars import ContextVar

REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Attach the current request ID to each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get() or "-"
        return True


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(
        level=level.upper(),
        format=(
            "%(asctime)s %(levelname)s [%(name)s] "
            "request_id=%(request_id)s %(message)s"
        ),
        handlers=[handler],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_id(request_id: str):
    """Set the request ID for logs emitted in the current context."""
    return REQUEST_ID.set(request_id)


def reset_request_id(token) -> None:
    """Reset the request ID context after request handling."""
    REQUEST_ID.reset(token)
