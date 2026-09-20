"""Liveness and readiness, which are different questions.

**Liveness** asks "is this process wedged?". It must not touch the database.
If it did, a database blip would make every container fail its liveness probe,
the orchestrator would kill them all, and a recoverable outage would become an
unrecoverable one.

**Readiness** asks "should traffic be routed here right now?". It does check
the database, because a container that cannot reach its database should be
taken out of the pool and put back when it can.

Conflating the two is one of the most common ways a Kubernetes deployment turns
a small problem into a large one.
"""

from __future__ import annotations

import logging

from django.db import connections
from django.db.utils import OperationalError
from django.http import HttpRequest, JsonResponse

log = logging.getLogger(__name__)


def live(request: HttpRequest) -> JsonResponse:
    """Always 200 while the process can serve a request at all."""
    return JsonResponse({"status": "ok"})


def ready(request: HttpRequest) -> JsonResponse:
    """200 only when every configured database answers."""
    checks: dict[str, str] = {}
    healthy = True

    for alias in connections:
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except OperationalError as exc:
            healthy = False
            checks[alias] = "unavailable"
            # The reason goes to the log, not to the response body: a probe
            # endpoint is usually reachable, and connection strings and host
            # names do not belong in something the world can curl.
            log.warning("readiness check failed for %s: %s", alias, exc)
        else:
            checks[alias] = "ok"

    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "databases": checks},
        status=200 if healthy else 503,
    )
