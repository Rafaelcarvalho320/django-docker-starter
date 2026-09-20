"""Request id propagation and its use in logs."""

from __future__ import annotations

import json
import logging

from django.test import Client

from config.logging import JSONFormatter
from core.middleware import HEADER_NAME, get_request_id


class TestHeader:
    def test_a_request_without_an_id_gets_one(self, client: Client) -> None:
        response = client.get("/health/live/")
        assert len(response[HEADER_NAME]) == 32

    def test_an_upstream_id_is_reused(self, client: Client) -> None:
        """Reusing is what stitches one user action across several services."""
        response = client.get("/health/live/", headers={HEADER_NAME: "abc-123"})
        assert response[HEADER_NAME] == "abc-123"

    def test_two_requests_get_different_ids(self, client: Client) -> None:
        first = client.get("/health/live/")[HEADER_NAME]
        second = client.get("/health/live/")[HEADER_NAME]
        assert first != second

    def test_the_id_survives_past_the_middleware_chain(self, client: Client) -> None:
        """Deliberate: Django logs 4xx and 5xx after the chain has returned.

        Clearing it on the way out would strip the id from exactly the log
        lines anyone greps for. See the comment in RequestIDMiddleware.
        """
        response = client.get("/health/live/")
        assert get_request_id() == response[HEADER_NAME]

    def test_each_request_replaces_the_previous_id(self, client: Client) -> None:
        """Which is what bounds the staleness the choice above accepts."""
        client.get("/health/live/", headers={HEADER_NAME: "first"})
        client.get("/health/live/", headers={HEADER_NAME: "second"})
        assert get_request_id() == "second"


class TestUntrustedInput:
    def test_an_overlong_id_is_replaced(self, client: Client) -> None:
        """The header is attacker-controlled and ends up in every log line."""
        response = client.get("/health/live/", headers={HEADER_NAME: "x" * 500})
        assert response[HEADER_NAME] != "x" * 500
        assert len(response[HEADER_NAME]) == 32

    def test_control_characters_are_rejected(self, client: Client) -> None:
        """Newlines in a log field are how log entries get forged."""
        response = client.get("/health/live/", headers={HEADER_NAME: "a b\nc"})
        assert response[HEADER_NAME] not in {"a b\nc", "a b"}

    def test_an_empty_header_is_replaced(self, client: Client) -> None:
        assert client.get("/health/live/", headers={HEADER_NAME: "  "})[HEADER_NAME]


class TestJSONLogging:
    def formatted(self, record: logging.LogRecord) -> dict[str, object]:
        return json.loads(JSONFormatter().format(record))

    def record(self, **extra: object) -> logging.LogRecord:
        record = logging.LogRecord(
            "app", logging.INFO, "f.py", 1, "hello %s", ("world",), None
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def test_one_json_object_per_line(self) -> None:
        payload = self.formatted(self.record())
        assert payload["message"] == "hello world"
        assert payload["level"] == "INFO"
        assert payload["logger"] == "app"

    def test_the_request_id_rides_along(self) -> None:
        assert self.formatted(self.record(request_id="r-1"))["request_id"] == "r-1"

    def test_extra_fields_are_kept(self) -> None:
        """So a call site can attach context without a second logging system."""
        payload = self.formatted(self.record(order_id=42, tenant="acme"))
        assert payload["order_id"] == 42
        assert payload["tenant"] == "acme"

    def test_an_unserializable_extra_does_not_break_the_line(self) -> None:
        payload = self.formatted(self.record(obj=object()))
        assert isinstance(payload["obj"], str)

    def test_exceptions_are_included(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = self.record()
            record.exc_info = sys.exc_info()
        assert "ValueError: boom" in str(self.formatted(record)["exception"])
