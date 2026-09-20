"""Settings entry point for static analysis only. Never used to serve.

mypy's Django plugin imports the settings module to learn the model layout,
and the real one refuses to import without ``DJANGO_SECRET_KEY`` — which is
exactly the behaviour worth keeping in production, and pure friction for a type
checker. This module supplies a throwaway value and then imports the real
settings unchanged, so ``mypy`` works on a clean checkout with nothing exported
and the production guard stays intact.

``setdefault``, so a real environment always wins.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "static-analysis-only-never-served")
os.environ.setdefault("DJANGO_DEBUG", "false")
os.environ.setdefault("DJANGO_STATIC_MANIFEST", "false")

from config.settings import *  # noqa: F403
