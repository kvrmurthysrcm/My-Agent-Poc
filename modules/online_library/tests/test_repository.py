from __future__ import annotations

import base64
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from modules.online_library import repository


class ScriptedCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.current = {}
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.executions.append((query, params))
        self.current = self.responses.pop(0) if self.responses else {}

    def fetchone(self):
        return self.current.get("one")

    def fetchall(self):
        return self.current.get("all", [])


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self._cursor


def install_connection(monkeypatch, *responses):
    cursor = ScriptedCursor(responses)
    monkeypatch.setattr(repository, "get_connection", lambda: FakeConnection(cursor))
    return cursor


def test_check_db_health_and_available_tables(monkeypatch):
    cursor = install_connection(
        monkeypatch,
        {"one": {"database": "library", "user": "sonar-safe-user"}},
    )

    assert repository.check_db_health() == {
        "status": "ok",
        "database": "library",
        "user": "sonar-safe-user",
    }
    assert cursor.executions[0][1] is None

    exposed = repository.list_available_tables()
    assert len(exposed) == len(repository.EXPOSED_TABLES)
    assert {"table": "resources", "order_column": "resource_id"} in exposed


def test_fetch_table_rows_rejects_unknown_table():
    with pytest.raises(ValueError, match="not exposed"):
        repository.fetch_table_rows("private_secrets", 10, 0)


def test_fetch_table_rows_uses_safe_identifier_and_json_conversion(monkeypatch):
    resource_id = UUID("00000000-0000-0000-0000-000000000001")
    cursor = install_connection(
        monkeypatch,
        {"all": [{"resource_id": resource_id, "price": Decimal("12.50"), "blob": b"abc"}]},
    )

    rows = repository.fetch_table_rows("resources", 25, 5)

    assert rows == [{"resource_id": str(resource_id), "price": 12.5, "blob": base64.b64encode(b"abc").decode("ascii")}]
    assert cursor.executions[0][1] == (25, 5)


def test_json_safe_converts_nested_database_types():
    identifier = UUID("00000000-0000-0000-0000-000000000002")
    instant = datetime(2026, 9, 16, 10, 30, tzinfo=timezone.utc)
    value = {
        "items": [identifier, date(2026, 9, 16), instant, Decimal("3.25"), b"xy", None],
    }

    assert repository._json_safe(value) == {
        "items": [str(identifier), "2026-09-16", instant.isoformat(), 3.25, "eHk=", None],
    }


def test_resource_optional_columns(monkeypatch):
    install_connection(
        monkeypatch,
        {"all": [{"column_name": "rag_enabled"}, {"column_name": "metadata_json"}]},
    )

    assert repository._resource_optional_columns() == {"rag_enabled", "metadata_json"}


def test_catalog_select_sql_handles_optional_and_legacy_schemas():
    modern = repository._catalog_select_sql(
        {"ingestion_status", "rag_enabled", "metadata_json", "storage_path"}
    )
    legacy = repository._catalog_select_sql(set())

    assert "r.ingestion_status as ingestion_status" in modern
    assert "r.rag_enabled as rag_enabled" in modern
    assert "r.metadata_json as metadata_json" in modern
    assert "r.storage_path as storage_path" in modern
    assert "null as ingestion_status" in legacy
    assert "'{}'::jsonb as metadata_json" in legacy


def test_catalog_conditions_build_all_supported_filters():
    conditions, params = repository._catalog_conditions(
        q="  dune  ",
        author=" Frank Herbert ",
        category="Science Fiction",
        tag="classic",
        publisher="Ace",
        language="English",
        tier=" premium ",
        status=" active ",
        published_from="1965-01-01",
        published_to="1965-12-31",
    )

    assert len(conditions) == 10
    assert params[:7] == ["%dune%"] * 7
    assert "%Frank Herbert%" in params
    assert "%Science Fiction%" in params
    assert "PREMIUM" in params
    assert "ACTIVE" in params
    assert params[-2:] == ["1965-01-01", "1965-12-31"]


def test_catalog_conditions_ignores_blank_filters():
    conditions, params = repository._catalog_conditions(
        q=" ", author=None, category="", tag=None, publisher=None,
        language=None, tier=None, status=None, published_from=None, published_to=None,
    )
    assert conditions == []
    assert params == []
    assert repository._clean(None) is None
    assert repository._clean("  ") is None
    assert repository._clean(" value ") == "value"


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("title", "r.title asc, r.created_at desc"),
        ("created_desc", "r.created_at desc, r.title asc"),
        ("created_asc", "r.created_at asc, r.title asc"),
        ("published_desc", "r.published_date desc nulls last, r.title asc"),
        ("published_asc", "r.published_date asc nulls last, r.title asc"),
        ("invalid", "r.title asc, r.created_at desc"),
    ],
)
def test_catalog_order_clause(sort, expected):
    assert repository._catalog_order_clause(sort) == expected


def test_catalog_row_normalizes_arrays_and_genre():
    row = repository._catalog_row({"category": "Fiction", "authors": None, "tags": []})
    assert row == {"category": "Fiction", "authors": [], "tags": [], "genre": "Fiction"}


def test_search_catalog_resources_executes_count_and_page_queries(monkeypatch):
    cursor = install_connection(
        monkeypatch,
        {"all": [{"column_name": "rag_enabled"}]},
        {"one": {"total": 2}},
        {"all": [{"resource_id": "1", "title": "Dune", "category": "Science Fiction", "authors": None, "tags": ["classic"]}]},
    )

    result = repository.search_catalog_resources(q="dune", limit=5, offset=10)

    assert result["total"] == 2
    assert result["count"] == 1
    assert result["resources"][0]["authors"] == []
    assert result["resources"][0]["genre"] == "Science Fiction"
    assert cursor.executions[-1][1][-2:] == [5, 10]


@pytest.mark.parametrize("row", [{"resource_id": "1", "category": "Fiction"}, None])
def test_get_catalog_resource_detail(monkeypatch, row):
    install_connection(
        monkeypatch,
        {"all": []},
        {"one": row},
    )

    result = repository.get_catalog_resource_detail("1")

    if row:
        assert result["resource_id"] == "1"
        assert result["authors"] == []
    else:
        assert result is None


def test_get_catalog_facets(monkeypatch):
    install_connection(
        monkeypatch,
        {"all": [{"value": "Fiction"}]},
        {"all": [{"value": "Mary Shelley"}]},
        {"all": [{"value": "classic"}]},
        {"all": [{"value": "English"}]},
        {"all": [{"tier_code": "FREE", "tier_name": "Free", "description": None}]},
    )

    facets = repository.get_catalog_facets()

    assert facets["categories"] == ["Fiction"]
    assert facets["genres"] == ["Fiction"]
    assert facets["authors"] == ["Mary Shelley"]
    assert facets["tags"] == ["classic"]
    assert facets["languages"] == ["English"]
    assert facets["subscription_tiers"][0]["tier_code"] == "FREE"


def test_search_rows_returns_compatible_named_and_generic_rows(monkeypatch):
    cursor = install_connection(
        monkeypatch,
        {"one": {"total": 1}},
        {"all": [{"author_id": "a1", "author_name": "Ursula Le Guin"}]},
    )

    result = repository._search_rows(
        table="authors",
        select_sql="select author_id, author_name from public.authors",
        where_clause="status = %s",
        order_clause="author_name asc",
        params=["ACTIVE"],
        limit=20,
        offset=0,
        rows_key="authors",
    )

    assert result["total"] == 1
    assert result["count"] == 1
    assert result["authors"] is result["rows"]
    assert cursor.executions[0][1] == ["ACTIVE"]
    assert cursor.executions[1][1] == ["ACTIVE", 20, 0]


@pytest.mark.parametrize(
    ("function_name", "kwargs", "expected_table", "expected_params"),
    [
        ("search_authors", {"q": "octavia", "status": "active"}, "authors", ["%octavia%", "%octavia%", "%octavia%", "ACTIVE"]),
        ("search_library_users", {"q": "reader", "status": "active", "approval_status": "approved"}, "library_users", ["%reader%", "%reader%", "%reader%", "ACTIVE", "APPROVED"]),
        ("search_user_subscriptions", {"q": "free", "tier": "free", "status": "active", "user_email": "reader@example.com"}, "user_subscriptions", ["%free%", "%free%", "%free%", "%free%", "FREE", "ACTIVE", "%reader@example.com%"]),
        ("search_approval_requests", {"q": "review", "status": "pending"}, "user_approval_requests", ["%review%", "%review%", "%review%", "PENDING"]),
    ],
)
def test_search_helpers_build_expected_queries(monkeypatch, function_name, kwargs, expected_table, expected_params):
    captured = {}

    def fake_search_rows(**values):
        captured.update(values)
        return {"count": 0}

    monkeypatch.setattr(repository, "_search_rows", fake_search_rows)

    result = getattr(repository, function_name)(**kwargs)

    assert result == {"count": 0}
    assert captured["table"] == expected_table
    assert captured["params"] == expected_params
    assert captured["limit"] == 20
    assert captured["offset"] == 0


@pytest.mark.parametrize(
    "function_name",
    ["search_authors", "search_library_users", "search_user_subscriptions", "search_approval_requests"],
)
def test_search_helpers_allow_no_filters(monkeypatch, function_name):
    captured = {}
    monkeypatch.setattr(repository, "_search_rows", lambda **values: captured.update(values) or {})

    getattr(repository, function_name)(status=None)

    assert captured["where_clause"] == "true"
    assert captured["params"] == []
