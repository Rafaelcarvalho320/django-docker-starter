"""Logging configuration.

Two formats for two audiences. Locally a human reads the terminal, so lines are
short and aligned. In a container a log aggregator reads stdout, so lines are
JSON, because the alternative is writing a grok pattern for every service and
maintaining it forever.

Both carry the request id, which is the whole reason the middleware exists: one
request scattered across twenty log lines is only followable if every line
says which request it belongs to.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.middleware import get_request_id


class RequestIDFilter(logging.Filter):
    """Attaches the current request id to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JSONFormatter(logging.Formatter):
    """One JSON object per line.

    Hand-written rather than pulling in a logging library: the whole
    requirement is "serialize a LogRecord", and this is the whole
    implementation.
    """

    RESERVED = frozenset(
        vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
    ) | {"message", "asctime", "taskName"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Anything passed as extra= rides along, so a call site can attach
        # structured context without a second logging system.
        for key, value in vars(record).items():
            if key not in self.RESERVED and key not in payload:
                payload[key] = _safe(value)
        return json.dumps(payload, default=str)


def _safe(value: Any) -> Any:
    if isinstance(value, str | int | float | bool | type(None)):
        return value
    return str(value)


def build_logging(level: str = "INFO", fmt: str = "json") -> dict[str, Any]:
    formatter = "json" if fmt.lower() == "json" else "console"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "config.logging.RequestIDFilter"},
        },
        "formatters": {
            "json": {"()": "config.logging.JSONFormatter"},
            "console": {
                "format": "%(asctime)s %(levelname)-8s [%(request_id)s] "
                "%(name)s: %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": formatter,
                "filters": ["request_id"],
            },
        },
        "root": {"handlers": ["stdout"], "level": level},
        "loggers": {
            # Django logs every 4xx and 5xx here; at WARNING it is useful
            # rather than a flood.
            "django.request": {"level": "WARNING", "propagate": True},
            # Left off on purpose. Turning it on logs every SQL statement,
            # which is a debugging tool, not a default.
            "django.db.backends": {"level": "WARNING", "propagate": True},
        },
    }
