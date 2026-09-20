"""The configuration layer itself."""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from config import settings as settings_module


class TestDatabaseUrl:
    def test_a_postgres_url_is_translated(self) -> None:
        parsed = settings_module.database_from_url(
            "postgres://user:pass@db.internal:5433/appdb"
        )
        assert parsed["ENGINE"] == "django.db.backends.postgresql"
        assert parsed["NAME"] == "appdb"
        assert parsed["USER"] == "user"
        assert parsed["PASSWORD"] == "pass"
        assert parsed["HOST"] == "db.internal"
        assert parsed["PORT"] == "5433"

    def test_a_password_with_url_escapes_is_decoded(self) -> None:
        """Passwords with @ or / in them arrive percent-encoded and must not."""
        parsed = settings_module.database_from_url(
            "postgres://user:p%40ss%2Fword@localhost:5432/appdb"
        )
        assert parsed["PASSWORD"] == "p@ss/word"

    def test_connections_are_reused_and_health_checked(self) -> None:
        """Without CONN_HEALTH_CHECKS, a reused dead connection is a 500."""
        parsed = settings_module.database_from_url("postgres://u:p@h:5432/d")
        assert parsed["CONN_MAX_AGE"] == 60
        assert parsed["CONN_HEALTH_CHECKS"] is True

    def test_a_sqlite_url_is_translated(self) -> None:
        parsed = settings_module.database_from_url("sqlite:///data/app.db")
        assert parsed["ENGINE"] == "django.db.backends.sqlite3"
        assert parsed["NAME"] == "data/app.db"

    def test_sqlite_in_memory(self) -> None:
        assert settings_module.database_from_url("sqlite://")["NAME"] == ":memory:"


class TestEnvHelpers:
    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_spellings(self, raw: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOME_FLAG", raw)
        assert settings_module.env_bool("SOME_FLAG") is True

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "", "maybe"])
    def test_everything_else_is_false(
        self, raw: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOME_FLAG", raw)
        assert settings_module.env_bool("SOME_FLAG") is False

    def test_a_nonsense_integer_falls_back_instead_of_crashing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A typo in a tuning knob must not stop the process booting."""
        monkeypatch.setenv("SOME_NUMBER", "lots")
        assert settings_module.env_int("SOME_NUMBER", 7) == 7

    def test_a_list_ignores_blanks_and_spacing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOME_LIST", " a , ,b,, c ")
        assert settings_module.env_list("SOME_LIST") == ["a", "b", "c"]


class TestSecretKeyGuard:
    @pytest.fixture(autouse=True)
    def restore_module(self) -> Iterator[None]:
        """Reloading leaves the module in whatever state the test wanted.

        The environment is restored here rather than left to monkeypatch: this
        fixture tears down before monkeypatch undoes its changes, so at this
        point the secret key it deleted is still missing and the reload would
        hit the very guard being tested.
        """
        yield
        os.environ["DJANGO_SECRET_KEY"] = "test-only-key-never-used-to-serve"
        os.environ["DJANGO_DEBUG"] = "false"
        importlib.reload(settings_module)

    def reload(self, monkeypatch: pytest.MonkeyPatch, **env: str) -> object:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(settings_module)

    def test_it_refuses_to_boot_without_a_key_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A default key that works in production is one that reaches it."""
        monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="DJANGO_SECRET_KEY must be set"):
            self.reload(monkeypatch, DJANGO_DEBUG="false")

    def test_development_gets_a_throwaway_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
        reloaded = self.reload(monkeypatch, DJANGO_DEBUG="true")
        assert reloaded.SECRET_KEY.startswith("insecure-development")  # type: ignore[attr-defined]

    def test_the_error_says_how_to_generate_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="token_urlsafe"):
            self.reload(monkeypatch, DJANGO_DEBUG="false")


class TestProductionPosture:
    def test_the_suite_runs_with_debug_off(self) -> None:
        """So the tests exercise the production configuration, not a softer one."""
        from django.conf import settings

        assert settings.DEBUG is False

    def test_secure_cookies_and_hsts_are_on_when_debug_is_off(self) -> None:
        from django.conf import settings

        assert settings.SESSION_COOKIE_SECURE is True
        assert settings.CSRF_COOKIE_SECURE is True
        assert settings.SECURE_HSTS_SECONDS > 0

    def test_the_proxy_ssl_header_is_off_unless_asked_for(self) -> None:
        """Trusting it unasked lets a client claim its plain request was https."""
        from django.conf import settings

        assert not hasattr(settings, "SECURE_PROXY_SSL_HEADER") or (
            settings.SECURE_PROXY_SSL_HEADER is None
        )

    def test_the_browsable_api_is_off_outside_debug(self) -> None:
        from django.conf import settings

        renderers = settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"]
        assert not any("Browsable" in renderer for renderer in renderers)

    def test_static_root_exists_so_whitenoise_does_not_warn(self) -> None:
        from django.conf import settings

        assert Path(settings.STATIC_ROOT).is_dir()
