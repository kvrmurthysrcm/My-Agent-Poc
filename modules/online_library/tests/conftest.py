"""Shared isolated fixtures for Online Library tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from types import TracebackType
from typing import Any, TypeAlias

import pytest
from fastapi.testclient import TestClient

from modules.online_library import api, repository

CursorResponse: TypeAlias = dict[str, Any]


class ScriptedCursor:
    """Provide predetermined database responses without opening PostgreSQL."""

    def __init__(self, responses: Sequence[CursorResponse]) -> None:
        """Initialize the cursor with ordered query responses.

        Args:
            responses: Responses consumed in the order their queries execute.
        """

        self._responses = list(responses)
        self._current: CursorResponse = {}
        self.executions: list[tuple[Any, Any]] = []

    def __enter__(self) -> ScriptedCursor:
        """Enter the cursor context.

        Returns:
            The scripted cursor.
        """

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Exit the cursor context without suppressing failures.

        Args:
            exc_type: The exception type raised in the context, if any.
            exc_value: The exception instance raised in the context, if any.
            traceback: The traceback raised in the context, if any.

        Returns:
            False so pytest observes any test failure.
        """

        return False

    def execute(self, query: Any, params: Any = None) -> None:
        """Record a query and make its next scripted response active.

        Args:
            query: The SQL query object issued by the repository.
            params: Parameters bound to the SQL query.
        """

        self.executions.append((query, params))
        self._current = self._responses.pop(0) if self._responses else {}

    def fetchone(self) -> dict[str, Any] | None:
        """Return the single row configured for the latest query.

        Returns:
            The configured row, or None when no row was supplied.
        """

        row = self._current.get("one")
        return row if isinstance(row, dict) else None

    def fetchall(self) -> list[dict[str, Any]]:
        """Return the rows configured for the latest query.

        Returns:
            A list of configured mapping rows.
        """

        rows = self._current.get("all", [])
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]


class ScriptedConnection:
    """Expose one scripted cursor through the psycopg context-manager shape."""

    def __init__(self, cursor: ScriptedCursor) -> None:
        """Store the cursor used by this connection.

        Args:
            cursor: The cursor to return for each cursor request.
        """

        self._cursor = cursor

    def __enter__(self) -> ScriptedConnection:
        """Enter the connection context.

        Returns:
            The scripted connection.
        """

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Exit the connection context without suppressing failures.

        Args:
            exc_type: The exception type raised in the context, if any.
            exc_value: The exception instance raised in the context, if any.
            traceback: The traceback raised in the context, if any.

        Returns:
            False so pytest observes any test failure.
        """

        return False

    def cursor(self) -> ScriptedCursor:
        """Return the configured cursor.

        Returns:
            The cursor that supplies scripted query results.
        """

        return self._cursor


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    """Yield a FastAPI client for request-level behavior tests.

    Yields:
        A client connected to the isolated Online Library application.
    """

    with TestClient(api.app) as client:
        yield client


@pytest.fixture
def install_repository_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., ScriptedCursor]:
    """Return a helper that replaces repository PostgreSQL access.

    Args:
        monkeypatch: Pytest helper that restores the repository connector
            after a test.

    Returns:
        A callable that installs responses and exposes their scripted cursor.
    """

    def install(*responses: CursorResponse) -> ScriptedCursor:
        """Install a fresh scripted connection for one test.

        Args:
            responses: Ordered cursor responses for repository queries.

        Returns:
            The cursor that records all executed queries.
        """

        cursor = ScriptedCursor(responses)
        monkeypatch.setattr(
            repository,
            "get_connection",
            lambda: ScriptedConnection(cursor),
        )
        return cursor

    return install
