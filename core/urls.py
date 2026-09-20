"""Operational endpoints. Deliberately outside /api/ and unauthenticated."""

from django.urls import path

from core import health

urlpatterns = [
    path("live/", health.live, name="health-live"),
    path("ready/", health.ready, name="health-ready"),
]
