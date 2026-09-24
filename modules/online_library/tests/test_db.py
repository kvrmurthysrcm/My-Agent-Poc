"""Tests for isolated PostgreSQL connection management."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from modules.online_library import db
from modules.online_library.config import DatabaseConfig


class TrackingConnection:
    """Track whether the database context manager closes its connection."""

    def __init__(self) -> None:
        """Initialize an open connection marker."""

        self.closed = False

    def close(self) -> None:
        """Record that the connection was closed."""

        self.closed = True


def test_get_connection_uses_loaded_configuration_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass all configuration fields to psycopg and close after use.

    Args:
        monkeypatch: Pytest helper used to isolate configuration and psycopg.
    """

    configuration = DatabaseConfig(
        host="db.example.test",
        port=6432,
        name="library",
        user="reader",
        password="reader-password",
    )
    connection = TrackingConnection()
    captured: dict[str, Any] = {}

    def load_config() -> DatabaseConfig:
        """Return the deterministic test configuration.

        Returns:
            The database configuration used by the test.
        """

        return configuration

    def connect(**kwargs: Any) -> TrackingConnection:
        """Record psycopg options and return the tracking connection.

        Args:
            **kwargs: Keyword options passed to psycopg.connect.

        Returns:
            The connection whose close call is asserted below.
        """

        captured.update(kwargs)
        return connection

    monkeypatch.setattr(db, "load_database_config", load_config)
    monkeypatch.setattr(db.psycopg, "connect", connect)

    with db.get_connection() as active_connection:
        assert active_connection is connection
        assert connection.closed is False

    assert connection.closed is True
    assert captured == {
        "host": "db.example.test",
        "port": 6432,
        "dbname": "library",
        "user": "reader",
        "password": "reader-password",
        "connect_timeout": 5,
        "row_factory": db.dict_row,
    }


def test_get_connection_propagates_psycopg_connect_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave connection failures visible to the API error boundary.

    Args:
        monkeypatch: Pytest helper used to replace psycopg.connect.
    """

    def connect(**kwargs: Any) -> TrackingConnection:
        """Raise the specific connection error expected by callers.

        Args:
            **kwargs: Keyword options supplied to psycopg.connect.

        Raises:
            psycopg.OperationalError: Always, to emulate an unreachable
                database.
        """

        raise psycopg.OperationalError("database unavailable")

    monkeypatch.setattr(db.psycopg, "connect", connect)

    with pytest.raises(psycopg.OperationalError, match="database unavailable"):
        with db.get_connection():
            pass
