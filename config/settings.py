"""Settings, driven entirely by environment variables.

One settings module, not a ``settings/`` package with base/dev/prod. Splitting
by environment reliably produces a production file nobody runs locally and
therefore nobody tests. Here every environment runs the same code and differs
only in its environment variables, which is also what the twelve-factor rule
is actually about.

Production-relevant behaviour is derived from ``DJANGO_DEBUG`` so the secure
setting is the one you get by default. ``manage.py check --deploy`` passes with
``DJANGO_DEBUG=false``, and CI enforces that it keeps passing.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import django_stubs_ext

# Lets Django's own generic classes accept type parameters at runtime, so that
# annotations like ModelAdmin[Item] are both checkable and importable. Without
# it those raise TypeError as soon as the admin is autodiscovered.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name, str(default)))
    except ValueError:
        return default


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        # Refusing to boot is the point. A default secret key that works in
        # production is a default secret key that reaches production.
        raise RuntimeError(
            "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false. "
            'Generate one with: python -c "import secrets; '
            'print(secrets.token_urlsafe(50))"'
        )
    # Suppressed on this line rather than project-wide: the literal is only
    # reachable with DEBUG on, and the branch above makes it impossible to
    # reach in production.
    SECRET_KEY = "insecure-development-key"  # noqa: S105

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "core",
    "items",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Above everything else that logs, so every log line in a request carries
    # the same id and one request can be followed end to end.
    "core.middleware.RequestIDMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


def database_from_url(url: str) -> dict[str, object]:
    """Translate a database URL into Django's DATABASES entry.

    Hand-rolled instead of pulling in dj-database-url: it is twenty lines, it
    is the only configuration parsing here, and a dependency that exists to
    avoid twenty lines is one to audit and upgrade forever.
    """
    parsed = urlparse(url)
    if parsed.scheme.startswith("sqlite"):
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": parsed.path.lstrip("/") or ":memory:",
        }
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": env_int("DJANGO_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
    }


DATABASE_URL = env("DATABASE_URL")
DATABASES = {
    "default": (
        database_from_url(DATABASE_URL)
        if DATABASE_URL
        else {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{name}"}
    for name in (
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    )
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The manifest backend rewrites every static URL to a hashed filename, which
# is what makes far-future caching safe. It also refuses to serve anything that
# is not in the manifest, so it only works after `collectstatic` has run: the
# container does that at build time, while a clean checkout has not. Hence the
# switch, defaulting to on wherever DEBUG is off.
USE_STATIC_MANIFEST = env_bool("DJANGO_STATIC_MANIFEST", not DEBUG)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if USE_STATIC_MANIFEST
            else "whitenoise.storage.CompressedStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    # Private by default. A new viewset is locked down unless it deliberately
    # opts out, which is the only ordering that survives someone adding an
    # endpoint in a hurry.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
if DEBUG:
    # The browsable API is genuinely useful locally and is an information leak
    # anywhere else, so it is added rather than removed.
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ]

# -- security ---------------------------------------------------------------
# All of this is what `manage.py check --deploy` asks for, and CI runs that
# check so the list cannot quietly rot.

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
    # Only when something in front really terminates TLS and sets the header.
    # Trusting it otherwise lets a client claim its plain request was secure.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

from config.logging import build_logging  # noqa: E402

LOGGING = build_logging(
    level=env("DJANGO_LOG_LEVEL", "INFO").upper(),
    fmt=env("DJANGO_LOG_FORMAT", "console" if DEBUG else "json"),
)

SENTRY_DSN = env("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
    except ImportError:  # pragma: no cover - optional dependency
        pass
    else:  # pragma: no cover - requires the optional dependency
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=env("SENTRY_ENVIRONMENT", "unknown"),
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", "0")),
            # Personal data does not belong in an error tracker by default.
            send_default_pii=False,
        )
