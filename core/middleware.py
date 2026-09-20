"""Request id propagation.

Every request gets an id, every log line during that request carries it, and
the response echoes it back in a header. That is what turns "something failed
around 14:32" into a single grep.

The id is kept in a ``ContextVar`` rather than on the request object, because
the logging filter that needs it has no access to the request. A ContextVar is
also correct under async and under threads, which a module-level global is not.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse

HEADER_NAME = "X-Request-ID"
_MAX_LENGTH = 64

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def new_request_id() -> str:
    return uuid.uuid4().hex


def _clean(value: str) -> str | None:
    """Accept an inbound id only if it is short and printable.

    The header comes from outside, and it ends up in log lines. An unbounded
    value is a way to flood the logs; a value with control characters is a way
    to forge log entries.
    """
    candidate = value.strip()
    if not candidate or len(candidate) > _MAX_LENGTH:
        return None
    if not all(char.isalnum() or char in "-_" for char in candidate):
        return None
    return candidate


class RequestIDMiddleware:
    """Reuses an upstream id when there is one, otherwise mints a new one.

    Reusing matters behind a gateway or between services: the id is what
    stitches one user action back together across several logs.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(HEADER_NAME, "")
        request_id = _clean(incoming) or new_request_id()

        # Deliberately set and left, not reset on the way out.
        #
        # Django logs every 4xx and 5xx from BaseHandler.get_response, which
        # runs *after* the whole middleware chain has returned. Resetting here
        # would therefore strip the id from exactly the log lines anyone ever
        # greps for: "Not Found: /x" and "Internal Server Error: /y".
        #
        # The cost is that a log line emitted between requests on the same
        # worker carries the previous request's id. That window is idle time,
        # every request overwrites the value as its first act, and a stale id
        # on an idle-time line is a far smaller problem than no id at all on
        # every error.
        _request_id.set(request_id)

        response = self.get_response(request)
        response[HEADER_NAME] = request_id
        return response
