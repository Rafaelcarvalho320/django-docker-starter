"""Liveness and readiness, which answer different questions."""

from __future__ import annotations

from unittest import mock

import pytest
from django.db.utils import OperationalError
from django.test import Client


def test_liveness_answers_without_a_database(client: Client) -> None:
    """No db fixture here on purpose: liveness must not touch the database.

    If it did, a database blip would fail every container's liveness probe,
    the orchestrator would kill them all, and a recoverable outage would stop
    being recoverable.
    """
    response = client.get("/health/live/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readiness_reports_ok_when_the_database_answers(client: Client) -> None:
    response = client.get("/health/ready/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["databases"]["default"] == "ok"


@pytest.mark.django_db
def test_readiness_returns_503_when_the_database_is_down(client: Client) -> None:
    """503 is what takes a container out of the load balancer pool."""
    with mock.patch(
        "django.db.backends.utils.CursorWrapper.execute",
        side_effect=OperationalError("connection refused"),
    ):
        response = client.get("/health/ready/")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


@pytest.mark.django_db
def test_the_failure_reason_is_logged_not_returned(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    """A probe endpoint is public; host names and DSNs stay out of the body."""
    with mock.patch(
        "django.db.backends.utils.CursorWrapper.execute",
        side_effect=OperationalError("could not connect to host db.internal:5432"),
    ):
        response = client.get("/health/ready/")

    assert "db.internal" not in response.content.decode()
    assert "db.internal" in caplog.text
