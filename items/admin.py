from __future__ import annotations

from django.contrib import admin

from items.models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin[Item]):
    list_display = ["name", "slug", "status", "quantity", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
