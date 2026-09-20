from __future__ import annotations

from rest_framework import viewsets

from items.models import Item
from items.serializers import ItemSerializer


class ItemViewSet(viewsets.ModelViewSet[Item]):
    """A conventional DRF viewset, wired to filtering, ordering and search."""

    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "name", "quantity"]
    search_fields = ["name", "description"]
    lookup_field = "slug"
