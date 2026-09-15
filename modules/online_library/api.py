from __future__ import annotations

import logging
import sys
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query

from .repository import (
    check_db_health,
    fetch_table_rows,
    get_catalog_facets,
    get_catalog_resource_detail,
    list_available_tables,
    search_approval_requests,
    search_authors,
    search_catalog_resources,
    search_library_users,
    search_user_subscriptions,
)
from .trace_context import install_log_record_factory, trace_context_middleware

install_log_record_factory()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s trace_id=%(trace_id)s span_id=%(span_id)s request_id=%(request_id)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
app = FastAPI(title="Online Library API POC")
app.middleware("http")(trace_context_middleware)


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


@app.get("/catalog/resources")
def catalog_resources(
    q: str | None = Query(None, description="Search title, description, author, category, tag, publisher, or ISBN."),
    author: str | None = Query(None),
    category: str | None = Query(None),
    genre: str | None = Query(None, description="Alias for category."),
    tag: str | None = Query(None),
    publisher: str | None = Query(None),
    language: str | None = Query(None),
    tier: str | None = Query(None),
    status: str | None = Query("ACTIVE"),
    published_from: str | None = Query(None),
    published_to: str | None = Query(None),
    sort: str = Query("title"),
    pagination: tuple[int, int] = Depends(_limit_query),
) -> dict[str, Any]:
    """Search online library catalog metadata without searching document chunks."""

    limit, offset = pagination
    return search_catalog_resources(
        q=q,
        author=author,
        category=category,
        genre=genre,
        tag=tag,
        publisher=publisher,
        language=language,
        tier=tier,
        status=status,
        published_from=published_from,
        published_to=published_to,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@app.get("/catalog/resources/{resource_id}")
def catalog_resource_detail(resource_id: str) -> dict[str, Any]:
    """Return one online library catalog resource with authors and tags. Test change in online library 13"""

    resource = get_catalog_resource_detail(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Catalog resource not found.")
    return {"resource": resource}


@app.get("/catalog/books/by-author")
def catalog_books_by_author(
    author: str = Query(..., min_length=1),
    status: str | None = Query("ACTIVE"),
    sort: str = Query("title"),
    pagination: tuple[int, int] = Depends(_limit_query),
) -> dict[str, Any]:
    """Search catalog resources by author name."""

    limit, offset = pagination
    return search_catalog_resources(author=author, status=status, sort=sort, limit=limit, offset=offset)


@app.get("/catalog/books/by-genre")
def catalog_books_by_genre(
    genre: str = Query(..., min_length=1),
    status: str | None = Query("ACTIVE"),
    sort: str = Query("title"),
    pagination: tuple[int, int] = Depends(_limit_query),
) -> dict[str, Any]:
    """Search catalog resources by genre/category name."""

    limit, offset = pagination
    return search_catalog_resources(genre=genre, status=status, sort=sort, limit=limit, offset=offset)


@app.get("/catalog/books/by-tag")
def catalog_books_by_tag(
    tag: str = Query(..., min_length=1),
    status: str | None = Query("ACTIVE"),
    sort: str = Query("title"),
    pagination: tuple[int, int] = Depends(_limit_query),
) -> dict[str, Any]:
    """Search catalog resources by tag name."""

    limit, offset = pagination
    return search_catalog_resources(tag=tag, status=status, sort=sort, limit=limit, offset=offset)


@app.get("/catalog/authors")
def catalog_authors(
    q: str | None = Query(None),
    status: str | None = Query("ACTIVE"),
    pagination: tuple[int, int] = Depends(_limit_query),
) -> dict[str, Any]:
    """Search author lookup records for NLQ and catalog UIs."""

    limit, offset = pagination
    return search_authors(q=q, status=status, limit=limit, offset=offset)


@app.get("/catalog/facets")
def catalog_facets() -> dict[str, Any]:
    """Return lookup values for catalog filters."""

    facets = get_catalog_facets()
    return {"facets": facets}


@app.get("/users/search")
def users_search(
    q: str | None = Query(None),
    status: str | None = Query(None),
    approval_status: str | None = Query(None),
    pagination: tuple[int, int] = Depends(_limit_query),
) -> dict[str, Any]:
    """Search library users by name, email, status, or approval status."""

    limit, offset = pagination
    return search_library_users(
        q=q,
        status=status,
        approval_status=approval_status,
        limit=limit,
        offset=offset,
    )


@app.get("/subscriptions/search")
def subscriptions_search(
    q: str | None = Query(None),
    tier: str | None = Query(None),
    status: str | None = Query(None),
    user_email: str | None = Query(None),
    pagination: tuple[int, int] = Depends(_limit_query),
) -> dict[str, Any]:
    """Search user subscription records with joined user and tier metadata."""

    limit, offset = pagination
    return search_user_subscriptions(
        q=q,
        tier=tier,
        status=status,
        user_email=user_email,
        limit=limit,
        offset=offset,
    )


@app.get("/approvals/search")
def approvals_search(
    q: str | None = Query(None),
    status: str | None = Query(None),
    pagination: tuple[int, int] = Depends(_limit_query),
) -> dict[str, Any]:
    """Search approval request records with joined user metadata."""

    limit, offset = pagination
    return search_approval_requests(q=q, status=status, limit=limit, offset=offset)


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
