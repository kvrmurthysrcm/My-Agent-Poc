from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query

from .repository import check_db_health, fetch_table_rows, list_available_tables

app = FastAPI(title="Online Library API POC")


# FastAPI injects these query parameters into every table endpoint through Depends.
# Keeping this in one helper avoids slightly different pagination behavior per route.
def _limit_query(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> tuple[int, int]:
    """Keep pagination rules consistent across all SELECT endpoints."""

    return limit, offset


def _rows_response(table_name: str, limit: int, offset: int) -> dict[str, Any]:
    """Build a consistent JSON envelope for SELECT * table results."""

    try:
        rows = fetch_table_rows(table_name, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "table": table_name,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "rows": rows,
    }


@app.get("/health/db")
def health_db() -> dict[str, Any]:
    """Check whether the API can connect to the Online Library database."""

    return check_db_health()


@app.get("/tables")
def tables() -> dict[str, Any]:
    """List non-empty database tables that have read-only API endpoints."""

    available_tables = list_available_tables()
    return {"count": len(available_tables), "tables": available_tables}


# The table endpoints below intentionally mirror the tables with data in the DB.
# Empty tables such as audit_log, downloads, and reviews do not get routes.
@app.get("/authors")
def authors(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.authors."""

    limit, offset = pagination
    return _rows_response("authors", limit, offset)


@app.get("/categories")
def categories(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.categories."""

    limit, offset = pagination
    return _rows_response("categories", limit, offset)


@app.get("/library-users")
def library_users(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.library_users."""

    limit, offset = pagination
    return _rows_response("library_users", limit, offset)


@app.get("/reading-progress")
def reading_progress(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.reading_progress."""

    limit, offset = pagination
    return _rows_response("reading_progress", limit, offset)


@app.get("/resource-authors")
def resource_authors(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.resource_authors."""

    limit, offset = pagination
    return _rows_response("resource_authors", limit, offset)


@app.get("/resource-tags")
def resource_tags(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.resource_tags."""

    limit, offset = pagination
    return _rows_response("resource_tags", limit, offset)


@app.get("/resources")
def resources(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.resources."""

    limit, offset = pagination
    return _rows_response("resources", limit, offset)


@app.get("/subscription-rules")
def subscription_rules(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.subscription_rules."""

    limit, offset = pagination
    return _rows_response("subscription_rules", limit, offset)


@app.get("/subscription-tiers")
def subscription_tiers(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.subscription_tiers."""

    limit, offset = pagination
    return _rows_response("subscription_tiers", limit, offset)


@app.get("/tags")
def tags(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.tags."""

    limit, offset = pagination
    return _rows_response("tags", limit, offset)


@app.get("/user-approval-requests")
def user_approval_requests(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.user_approval_requests."""

    limit, offset = pagination
    return _rows_response("user_approval_requests", limit, offset)


@app.get("/user-bookshelf")
def user_bookshelf(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.user_bookshelf."""

    limit, offset = pagination
    return _rows_response("user_bookshelf", limit, offset)


@app.get("/user-subscriptions")
def user_subscriptions(pagination: tuple[int, int] = Depends(_limit_query)) -> dict[str, Any]:
    """Return SELECT * data from public.user_subscriptions."""

    limit, offset = pagination
    return _rows_response("user_subscriptions", limit, offset)
