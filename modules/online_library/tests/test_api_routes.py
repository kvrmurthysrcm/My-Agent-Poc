"""Generated route tests for the Online Library FastAPI application."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from modules.online_library import api


_TABLE_ENDPOINTS = (
    ("/authors", "authors"),
    ("/categories", "categories"),
    ("/library-users", "library_users"),
    ("/reading-progress", "reading_progress"),
    ("/resource-authors", "resource_authors"),
    ("/resource-tags", "resource_tags"),
    ("/resources", "resources"),
    ("/subscription-rules", "subscription_rules"),
    ("/subscription-tiers", "subscription_tiers"),
    ("/tags", "tags"),
    ("/user-approval-requests", "user_approval_requests"),
    ("/user-bookshelf", "user_bookshelf"),
    ("/user-subscriptions", "user_subscriptions"),
)


def test_catalog_resources_forwards_default_filters(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward documented default query values to the catalog repository.

    Args:
        api_client: Isolated client used to call the FastAPI route.
        monkeypatch: Pytest helper used to replace the repository dependency.
    """

    captured: dict[str, Any] = {}

    def search_catalog_resources(**kwargs: Any) -> dict[str, Any]:
        """Capture route arguments and return an empty catalog page.

        Args:
            **kwargs: Arguments forwarded by the catalog route.

        Returns:
            A valid empty catalog response.
        """

        captured.update(kwargs)
        return {
            "total": 0,
            "limit": kwargs["limit"],
            "offset": kwargs["offset"],
            "count": 0,
            "resources": [],
        }

    monkeypatch.setattr(
        api,
        "search_catalog_resources",
        search_catalog_resources,
    )

    response = api_client.get("/catalog/resources")

    assert response.status_code == 200
    assert response.json()["resources"] == []
    assert captured == {
        "q": None,
        "author": None,
        "category": None,
        "genre": None,
        "tag": None,
        "publisher": None,
        "language": None,
        "tier": None,
        "status": "ACTIVE",
        "published_from": None,
        "published_to": None,
        "sort": "title",
        "limit": 20,
        "offset": 0,
    }


@pytest.mark.parametrize(
    ("path", "parameter", "expected_keyword"),
    (
        ("/catalog/books/by-author", "author", "author"),
        ("/catalog/books/by-genre", "genre", "genre"),
        ("/catalog/books/by-tag", "tag", "tag"),
    ),
)
def test_catalog_book_routes_forward_filters(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    parameter: str,
    expected_keyword: str,
) -> None:
    """Forward each specialized book lookup filter to the catalog search.

    Args:
        api_client: Isolated client used to call the FastAPI route.
        monkeypatch: Pytest helper used to replace the catalog search
            dependency.
        path: Specialized catalog route under test.
        parameter: Required query-parameter name for the route.
        expected_keyword: Repository keyword expected to receive the parameter.
    """

    captured: dict[str, Any] = {}

    def search_catalog_resources(**kwargs: Any) -> dict[str, Any]:
        """Capture the specialized filter and return an empty page.

        Args:
            **kwargs: Arguments forwarded by the specialized route.

        Returns:
            A valid empty catalog response.
        """

        captured.update(kwargs)
        return {
            "total": 0,
            "limit": kwargs["limit"],
            "offset": kwargs["offset"],
            "count": 0,
            "resources": [],
        }

    monkeypatch.setattr(
        api,
        "search_catalog_resources",
        search_catalog_resources,
    )

    response = api_client.get(
        path,
        params={
            parameter: "Example value",
            "status": "INACTIVE",
            "sort": "created_desc",
            "limit": 1,
            "offset": 100,
        },
    )

    assert response.status_code == 200
    assert captured[expected_keyword] == "Example value"
    assert captured["status"] == "INACTIVE"
    assert captured["sort"] == "created_desc"
    assert captured["limit"] == 1
    assert captured["offset"] == 100


@pytest.mark.parametrize(
    "path",
    (
        "/catalog/books/by-author",
        "/catalog/books/by-genre",
        "/catalog/books/by-tag",
    ),
)
def test_catalog_book_routes_require_their_lookup_value(
    api_client: TestClient,
    path: str,
) -> None:
    """Reject specialized catalog requests that omit their required filter.

    Args:
        api_client: Isolated client used to call the FastAPI route.
        path: Specialized catalog route under test.
    """

    response = api_client.get(path)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "dependency_name", "params", "expected"),
    (
        (
            "/catalog/authors",
            "search_authors",
            {"q": "Octavia", "status": "INACTIVE", "limit": 3, "offset": 1},
            {"q": "Octavia", "status": "INACTIVE", "limit": 3, "offset": 1},
        ),
        (
            "/users/search",
            "search_library_users",
            {
                "q": "reader",
                "status": "ACTIVE",
                "approval_status": "APPROVED",
                "limit": 4,
                "offset": 2,
            },
            {
                "q": "reader",
                "status": "ACTIVE",
                "approval_status": "APPROVED",
                "limit": 4,
                "offset": 2,
            },
        ),
        (
            "/subscriptions/search",
            "search_user_subscriptions",
            {
                "q": "free",
                "tier": "FREE",
                "status": "ACTIVE",
                "user_email": "reader@example.test",
                "limit": 5,
                "offset": 3,
            },
            {
                "q": "free",
                "tier": "FREE",
                "status": "ACTIVE",
                "user_email": "reader@example.test",
                "limit": 5,
                "offset": 3,
            },
        ),
        (
            "/approvals/search",
            "search_approval_requests",
            {"q": "review", "status": "PENDING", "limit": 6, "offset": 4},
            {"q": "review", "status": "PENDING", "limit": 6, "offset": 4},
        ),
    ),
)
def test_search_routes_forward_filters(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    dependency_name: str,
    params: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Forward search filters to the matching repository function.

    Args:
        api_client: Isolated client used to call the FastAPI route.
        monkeypatch: Pytest helper used to replace the repository dependency.
        path: Search route under test.
        dependency_name: Imported repository function called by the route.
        params: Query parameters sent to the route.
        expected: Keyword arguments expected by the repository function.
    """

    captured: dict[str, Any] = {}

    def search_dependency(**kwargs: Any) -> dict[str, Any]:
        """Capture route arguments and return a compatible empty result.

        Args:
            **kwargs: Arguments forwarded by the search route.

        Returns:
            An empty search response.
        """

        captured.update(kwargs)
        return {"count": 0, "rows": []}

    monkeypatch.setattr(api, dependency_name, search_dependency)

    response = api_client.get(path, params=params)

    assert response.status_code == 200
    assert captured == expected


def test_health_and_table_routes_return_repository_data(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose health and table metadata without opening a real database.

    Args:
        api_client: Isolated client used to call the FastAPI routes.
        monkeypatch: Pytest helper used to replace repository dependencies.
    """

    def check_db_health() -> dict[str, str]:
        """Return a deterministic healthy database response.

        Returns:
            The database health payload expected from the repository.
        """

        return {"status": "ok", "database": "library"}

    def list_available_tables() -> list[dict[str, str]]:
        """Return a deterministic exposed-table response.

        Returns:
            The table metadata expected from the repository.
        """

        return [{"table": "resources", "order_column": "resource_id"}]

    monkeypatch.setattr(api, "check_db_health", check_db_health)
    monkeypatch.setattr(
        api,
        "list_available_tables",
        list_available_tables,
    )

    health_response = api_client.get("/health/db")
    tables_response = api_client.get("/tables")

    assert health_response.json() == {"status": "ok", "database": "library"}
    assert tables_response.json() == {
        "count": 1,
        "tables": [{"table": "resources", "order_column": "resource_id"}],
    }


@pytest.mark.parametrize(("path", "table_name"), _TABLE_ENDPOINTS)
def test_table_endpoints_return_paginated_rows(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    table_name: str,
) -> None:
    """Map every exposed table endpoint to its repository table name.

    Args:
        api_client: Isolated client used to call the FastAPI route.
        monkeypatch: Pytest helper used to replace table-row access.
        path: Table endpoint under test.
        table_name: Repository table expected from the route.
    """

    captured: list[tuple[str, int, int]] = []

    def fetch_table_rows(
        requested_table: str,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, str]]:
        """Capture pagination input and return one deterministic row.

        Args:
            requested_table: Table requested by the route.
            limit: Maximum number of rows requested.
            offset: Starting position requested by the route.

        Returns:
            One row that makes the response envelope observable.
        """

        captured.append((requested_table, limit, offset))
        return [{"table": requested_table}]

    monkeypatch.setattr(api, "fetch_table_rows", fetch_table_rows)

    response = api_client.get(path, params={"limit": 100, "offset": 0})

    assert response.status_code == 200
    assert response.json() == {
        "table": table_name,
        "limit": 100,
        "offset": 0,
        "count": 1,
        "rows": [{"table": table_name}],
    }
    assert captured == [(table_name, 100, 0)]


def test_table_endpoint_translates_repository_value_errors(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return a client-safe 404 when a table is not exposed.

    Args:
        api_client: Isolated client used to call the FastAPI route.
        monkeypatch: Pytest helper used to replace table-row access.
    """

    def fetch_table_rows(
        table_name: str,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, str]]:
        """Raise the repository validation error translated by the API.

        Args:
            table_name: Requested table name.
            limit: Requested maximum row count.
            offset: Requested starting row.

        Raises:
            ValueError: Always, to exercise the API error translation.
        """

        raise ValueError(f"Table '{table_name}' is not exposed")

    monkeypatch.setattr(api, "fetch_table_rows", fetch_table_rows)

    response = api_client.get("/authors")

    assert response.status_code == 404
    assert response.json() == {"detail": "Table 'authors' is not exposed"}


@pytest.mark.parametrize(
    "params",
    (
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ),
)
def test_pagination_rejects_out_of_range_values(
    api_client: TestClient,
    params: dict[str, int],
) -> None:
    """Reject pagination values outside the route contract.

    Args:
        api_client: Isolated client used to call the FastAPI route.
        params: Invalid pagination parameters sent to the route.
    """

    response = api_client.get("/authors", params=params)

    assert response.status_code == 422
