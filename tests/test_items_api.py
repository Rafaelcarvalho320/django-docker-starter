"""The sample API, which exists so the template ships something that runs."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.test import Client

from items.models import Item

pytestmark = pytest.mark.django_db


@pytest.fixture
def signed_in(client: Client, django_user_model: type[User]) -> Client:
    user = django_user_model.objects.create_user("dev", password="dev-password")
    client.force_login(user)
    return client


@pytest.fixture
def catalogue() -> list[Item]:
    return [
        Item.objects.create(name="Widget", slug="widget", status=Item.Status.ACTIVE),
        Item.objects.create(name="Gadget", slug="gadget", status=Item.Status.DRAFT),
        Item.objects.create(
            name="Gizmo", slug="gizmo", status=Item.Status.ACTIVE, quantity=7
        ),
    ]


class TestPermissions:
    def test_the_api_is_closed_to_strangers(self, client: Client) -> None:
        """Private by default: a new viewset is locked unless it opts out."""
        assert client.get("/api/items/").status_code in {401, 403}

    def test_a_signed_in_user_gets_through(self, signed_in: Client) -> None:
        assert signed_in.get("/api/items/").status_code == 200


class TestCrud:
    def test_listing_is_paginated(
        self, signed_in: Client, catalogue: list[Item]
    ) -> None:
        body = signed_in.get("/api/items/").json()
        assert body["count"] == 3
        assert len(body["results"]) == 3

    def test_creating(self, signed_in: Client) -> None:
        response = signed_in.post(
            "/api/items/",
            data={"name": "New", "slug": "new", "quantity": 2},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert Item.objects.get(slug="new").quantity == 2

    def test_a_duplicate_slug_is_rejected(
        self, signed_in: Client, catalogue: list[Item]
    ) -> None:
        response = signed_in.post(
            "/api/items/",
            data={"name": "Another", "slug": "widget"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "slug" in response.json()

    def test_lookup_is_by_slug_not_id(
        self, signed_in: Client, catalogue: list[Item]
    ) -> None:
        assert signed_in.get("/api/items/widget/").json()["name"] == "Widget"

    def test_updating(self, signed_in: Client, catalogue: list[Item]) -> None:
        response = signed_in.patch(
            "/api/items/widget/",
            data={"quantity": 99},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert Item.objects.get(slug="widget").quantity == 99

    def test_deleting(self, signed_in: Client, catalogue: list[Item]) -> None:
        assert signed_in.delete("/api/items/widget/").status_code == 204
        assert not Item.objects.filter(slug="widget").exists()

    def test_timestamps_are_read_only(
        self, signed_in: Client, catalogue: list[Item]
    ) -> None:
        original = Item.objects.get(slug="widget").created_at
        signed_in.patch(
            "/api/items/widget/",
            data={"created_at": "2000-01-01T00:00:00Z"},
            content_type="application/json",
        )
        assert Item.objects.get(slug="widget").created_at == original


class TestQuerying:
    def test_filtering_by_status(
        self, signed_in: Client, catalogue: list[Item]
    ) -> None:
        body = signed_in.get("/api/items/?status=active").json()
        assert body["count"] == 2

    def test_searching(self, signed_in: Client, catalogue: list[Item]) -> None:
        body = signed_in.get("/api/items/?search=widg").json()
        assert [row["slug"] for row in body["results"]] == ["widget"]

    def test_ordering(self, signed_in: Client, catalogue: list[Item]) -> None:
        body = signed_in.get("/api/items/?ordering=name").json()
        assert [row["name"] for row in body["results"]] == [
            "Gadget",
            "Gizmo",
            "Widget",
        ]


class TestAdmin:
    def test_the_admin_login_page_renders(self, client: Client) -> None:
        """Proves the static file pipeline works under production settings."""
        assert client.get("/admin/login/").status_code == 200
