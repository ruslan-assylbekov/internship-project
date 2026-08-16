"""Logging setup.

The app used to ``print`` its request log, which cannot be filtered by level,
carries no timestamp, and is invisible to anything that collects logs from a
container. Records are emitted as ``key=value`` pairs so a log shipper can
parse them without a regex per message.
"""

import logging
import sys
from contextvars import ContextVar

from src.core.config import get_settings

# Set once so repeated calls (imports, test runs, reload workers) do not stack
# duplicate handlers on the root logger.
_configured = False

# Written by the request middleware and read by the filter below, so a log line
# emitted deep inside a service still carries the request it belongs to without
# every function having to accept and forward an id.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


class KeyValueFormatter(logging.Formatter):
    """``ts=... level=... logger=... msg="..." k=v`` for extras.

    Anything passed via ``logger.info(..., extra={...})`` is appended, so
    request fields stay machine-readable instead of being baked into prose.
    """

    _RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
        "message",
        "asctime",
        "taskName",
        # uvicorn attaches its own pre-colourised copy of the message, which
        # would put raw ANSI escapes into a line meant to be machine-parsed.
        "color_message",
    }

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"ts={self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z')} "
            f"level={record.levelname} "
            f"logger={record.name} "
            f'msg="{record.getMessage()}"'
        )
        extras = " ".join(
            f"{key}={value}"
            for key, value in record.__dict__.items()
            if key not in self._RESERVED and not key.startswith("_")
        )
        line = f"{base} {extras}" if extras else base
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KeyValueFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(get_settings().log_level.upper())

    # uvicorn installs its own handlers; let them propagate to ours instead so
    # every line shares one format.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    _configured = True
