from __future__ import annotations

import base64
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import sql

from .db import get_connection


# Only tables with data are exposed. Empty tables are intentionally omitted
# because this POC creates select APIs only where there is something useful to fetch.
EXPOSED_TABLES: dict[str, str] = {
    "authors": "author_id",
    "categories": "category_id",
    "library_users": "user_id",
    "reading_progress": "progress_id",
    "resource_authors": "resource_id",
    "resource_tags": "resource_id",
    "resources": "resource_id",
    "subscription_rules": "rule_id",
    "subscription_tiers": "tier_code",
    "tags": "tag_id",
    "user_approval_requests": "approval_request_id",
    "user_bookshelf": "bookshelf_id",
    "user_subscriptions": "subscription_id",
}


def check_db_health() -> dict[str, Any]:
    """Run a tiny query so the API can prove the DB login still works."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select current_database() as database, current_user as user")
            row = cur.fetchone()
    return {"status": "ok", **_json_safe(row)}


def list_available_tables() -> list[dict[str, str]]:
    """Return the tables that have API endpoints in this POC."""

    return [
        {"table": table_name, "order_column": order_column}
        for table_name, order_column in EXPOSED_TABLES.items()
    ]


def fetch_table_rows(table_name: str, limit: int, offset: int) -> list[dict[str, Any]]:
    """Execute SELECT * for an allowed table using safe SQL identifiers."""

    if table_name not in EXPOSED_TABLES:
        raise ValueError(f"Table '{table_name}' is not exposed by this API.")

    order_column = EXPOSED_TABLES[table_name]
    query = sql.SQL(
        """
        select *
        from public.{table_name}
        order by {order_column}
        limit %s offset %s
        """
    ).format(
        table_name=sql.Identifier(table_name),
        order_column=sql.Identifier(order_column),
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit, offset))
            rows = cur.fetchall()

    # psycopg returns Python-native values such as UUID, date, Decimal, and bytes.
    # FastAPI can encode many of them, but bytea needs a deterministic JSON form.
    return [_json_safe(row) for row in rows]


def _json_safe(value: Any) -> Any:
    """Convert PostgreSQL/Python values into JSON-safe values."""

    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value
