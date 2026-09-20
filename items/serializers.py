from __future__ import annotations

from rest_framework import serializers

from items.models import Item


class ItemSerializer(serializers.ModelSerializer[Item]):
    class Meta:
        model = Item
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "status",
            "quantity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
