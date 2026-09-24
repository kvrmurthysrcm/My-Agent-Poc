"""Additional generated repository tests using the shared mock fixture."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any, Protocol

from modules.online_library import repository


class ScriptedCursorProtocol(Protocol):
    """Describe the cursor details asserted by repository tests."""

    executions: list[tuple[Any, Any]]


def test_fetch_table_rows_uses_shared_mock_fixture(
    install_repository_connection: Callable[..., ScriptedCursorProtocol],
) -> None:
    """Serialize database values while using the reusable connection fixture.

    Args:
        install_repository_connection: Fixture that replaces PostgreSQL access.
    """

    cursor = install_repository_connection(
        {
            "all": [
                {"title": "Example", "price": Decimal("9.99")}
            ]
        }
    )

    rows = repository.fetch_table_rows("authors", limit=1, offset=0)

    assert rows == [{"title": "Example", "price": 9.99}]
    assert cursor.executions[0][1] == (1, 0)


def test_search_catalog_resources_uses_genre_when_category_is_absent(
    install_repository_connection: Callable[..., ScriptedCursorProtocol],
) -> None:
    """Apply the genre alias when the explicit category filter is absent.

    Args:
        install_repository_connection: Fixture that replaces PostgreSQL access.
    """

    cursor = install_repository_connection(
        {"all": []},
        {"one": {"total": 0}},
        {"all": []},
    )

    result = repository.search_catalog_resources(
        category=None,
        genre="Science Fiction",
        status=None,
        limit=100,
        offset=0,
        sort="unknown-sort",
    )

    assert result == {
        "total": 0,
        "limit": 100,
        "offset": 0,
        "count": 0,
        "resources": [],
    }
    assert cursor.executions[1][1] == ["%Science Fiction%"]
    assert cursor.executions[2][1] == ["%Science Fiction%", 100, 0]
    assert "order by r.title asc, r.created_at desc" in cursor.executions[2][0]


def test_search_catalog_resources_prioritizes_category_over_genre(
    install_repository_connection: Callable[..., ScriptedCursorProtocol],
) -> None:
    """Prefer the explicit category filter over its genre alias.

    Args:
        install_repository_connection: Fixture that replaces PostgreSQL access.
    """

    cursor = install_repository_connection(
        {"all": []},
        {"one": {"total": 0}},
        {"all": []},
    )

    repository.search_catalog_resources(
        category="Fantasy",
        genre="Ignored Alias",
        status=None,
    )

    assert cursor.executions[1][1] == ["%Fantasy%"]


def test_catalog_row_normalizes_missing_array_values() -> None:
    """Return empty arrays and a null genre for a sparse catalog row."""

    assert repository._catalog_row({"category": None}) == {
        "category": None,
        "authors": [],
        "tags": [],
        "genre": None,
    }
