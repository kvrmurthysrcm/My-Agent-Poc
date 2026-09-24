"""Tests for Online Library database configuration."""

from __future__ import annotations

import pytest

from modules.online_library.config import DatabaseConfig, load_database_config


_DATABASE_ENVIRONMENT_KEYS = (
    "ONLINE_LIBRARY_DB_HOST",
    "ONLINE_LIBRARY_DB_PORT",
    "ONLINE_LIBRARY_DB_NAME",
    "ONLINE_LIBRARY_DB_USER",
    "ONLINE_LIBRARY_DB_PASSWORD",
)


def test_load_database_config_uses_local_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the documented POC settings when no environment values exist.

    Args:
        monkeypatch: Pytest helper used to clear database environment
            variables.
    """

    for environment_key in _DATABASE_ENVIRONMENT_KEYS:
        monkeypatch.delenv(environment_key, raising=False)

    assert load_database_config() == DatabaseConfig(
        host="localhost",
        port=5432,
        name="online_library",
        user="library_user",
        password="library_pass",
    )


def test_load_database_config_uses_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply every supplied database environment override.

    Args:
        monkeypatch: Pytest helper used to define database environment
            variables.
    """

    monkeypatch.setenv("ONLINE_LIBRARY_DB_HOST", "postgres.internal")
    monkeypatch.setenv("ONLINE_LIBRARY_DB_PORT", "15432")
    monkeypatch.setenv("ONLINE_LIBRARY_DB_NAME", "catalog")
    monkeypatch.setenv("ONLINE_LIBRARY_DB_USER", "catalog_reader")
    monkeypatch.setenv("ONLINE_LIBRARY_DB_PASSWORD", "secret-value")

    assert load_database_config() == DatabaseConfig(
        host="postgres.internal",
        port=15432,
        name="catalog",
        user="catalog_reader",
        password="secret-value",
    )


def test_load_database_config_rejects_a_non_numeric_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surface a malformed port rather than silently connecting elsewhere.

    Args:
        monkeypatch: Pytest helper used to define the malformed port value.
    """

    monkeypatch.setenv("ONLINE_LIBRARY_DB_PORT", "not-a-port")

    with pytest.raises(ValueError, match="invalid literal"):
        load_database_config()
