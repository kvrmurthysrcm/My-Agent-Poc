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


def search_catalog_resources(
    *,
    q: str | None = None,
    author: str | None = None,
    category: str | None = None,
    genre: str | None = None,
    tag: str | None = None,
    publisher: str | None = None,
    language: str | None = None,
    tier: str | None = None,
    status: str | None = "ACTIVE",
    published_from: str | None = None,
    published_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
    sort: str = "title",
) -> dict[str, Any]:
    """Search catalog resources by structured metadata columns and lookup tables."""

    optional_columns = _resource_optional_columns()
    conditions, params = _catalog_conditions(
        q=q,
        author=author,
        category=category or genre,
        tag=tag,
        publisher=publisher,
        language=language,
        tier=tier,
        status=status,
        published_from=published_from,
        published_to=published_to,
    )
    where_clause = " and ".join(conditions) if conditions else "true"
    order_clause = _catalog_order_clause(sort)
    select_sql = _catalog_select_sql(optional_columns)

    query = f"""
        {select_sql}
        from public.resources r
        left join public.categories c on c.category_id = r.category_id
        where {where_clause}
        order by {order_clause}
        limit %s offset %s
    """
    count_query = f"""
        select count(*) as total
        from public.resources r
        left join public.categories c on c.category_id = r.category_id
        where {where_clause}
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(count_query, params)
            total = int(cur.fetchone()["total"])
            cur.execute(query, [*params, limit, offset])
            rows = cur.fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "resources": [_catalog_row(row) for row in rows],
    }


def get_catalog_resource_detail(resource_id: str) -> dict[str, Any] | None:
    """Return one catalog resource with structured metadata arrays."""

    optional_columns = _resource_optional_columns()
    select_sql = _catalog_select_sql(optional_columns)
    query = f"""
        {select_sql}
        from public.resources r
        left join public.categories c on c.category_id = r.category_id
        where r.resource_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (resource_id,))
            row = cur.fetchone()
    return _catalog_row(row) if row else None


def get_catalog_facets() -> dict[str, Any]:
    """Return distinct lookup values useful for catalog search filters."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select category_name as value
                from public.categories
                where status = 'ACTIVE'
                order by category_name
                """
            )
            categories = [row["value"] for row in cur.fetchall()]

            cur.execute(
                """
                select author_name as value
                from public.authors
                where status = 'ACTIVE'
                order by author_name
                """
            )
            authors = [row["value"] for row in cur.fetchall()]

            cur.execute("select tag_name as value from public.tags order by tag_name")
            tags = [row["value"] for row in cur.fetchall()]

            cur.execute(
                """
                select distinct language as value
                from public.resources
                where language is not null and language <> ''
                order by language
                """
            )
            languages = [row["value"] for row in cur.fetchall()]

            cur.execute(
                """
                select tier_code, tier_name, description
                from public.subscription_tiers
                where status = 'ACTIVE'
                order by display_order, tier_code
                """
            )
            tiers = [_json_safe(row) for row in cur.fetchall()]

    return {
        "categories": categories,
        "genres": categories,
        "authors": authors,
        "tags": tags,
        "languages": languages,
        "subscription_tiers": tiers,
    }


def search_authors(
    *,
    q: str | None = None,
    status: str | None = "ACTIVE",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search author lookup records by name, bio, country, and status."""

    conditions: list[str] = []
    params: list[Any] = []
    if _clean(q):
        pattern = f"%{_clean(q)}%"
        conditions.append("(author_name ilike %s or coalesce(bio, '') ilike %s or coalesce(country, '') ilike %s)")
        params.extend([pattern, pattern, pattern])
    if _clean(status):
        conditions.append("status = %s")
        params.append(_clean(status).upper())

    return _search_rows(
        table="authors",
        select_sql="select author_id, author_name, bio, country, status, created_at, updated_at from public.authors",
        where_clause=" and ".join(conditions) if conditions else "true",
        order_clause="author_name asc",
        params=params,
        limit=limit,
        offset=offset,
        rows_key="authors",
    )


def search_library_users(
    *,
    q: str | None = None,
    status: str | None = None,
    approval_status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search library users by name, email, Keycloak id, status, or approval status."""

    conditions: list[str] = []
    params: list[Any] = []
    if _clean(q):
        pattern = f"%{_clean(q)}%"
        conditions.append("(full_name ilike %s or email ilike %s or coalesce(keycloak_user_id, '') ilike %s)")
        params.extend([pattern, pattern, pattern])
    if _clean(status):
        conditions.append("status = %s")
        params.append(_clean(status).upper())
    if _clean(approval_status):
        conditions.append("approval_status = %s")
        params.append(_clean(approval_status).upper())

    return _search_rows(
        table="library_users",
        select_sql="""
            select user_id, full_name, email, keycloak_user_id, status, approval_status,
                   approved_by, approved_at, rejected_reason, created_at, updated_at
            from public.library_users
        """,
        where_clause=" and ".join(conditions) if conditions else "true",
        order_clause="created_at desc, full_name asc",
        params=params,
        limit=limit,
        offset=offset,
        rows_key="users",
    )


def search_user_subscriptions(
    *,
    q: str | None = None,
    tier: str | None = None,
    status: str | None = None,
    user_email: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search user subscriptions with joined user and tier metadata."""

    conditions: list[str] = []
    params: list[Any] = []
    if _clean(q):
        pattern = f"%{_clean(q)}%"
        conditions.append("(u.full_name ilike %s or u.email ilike %s or us.tier_code ilike %s or st.tier_name ilike %s)")
        params.extend([pattern, pattern, pattern, pattern])
    if _clean(tier):
        conditions.append("us.tier_code = %s")
        params.append(_clean(tier).upper())
    if _clean(status):
        conditions.append("us.status = %s")
        params.append(_clean(status).upper())
    if _clean(user_email):
        conditions.append("u.email ilike %s")
        params.append(f"%{_clean(user_email)}%")

    return _search_rows(
        table="user_subscriptions",
        select_sql="""
            select us.subscription_id, us.user_id, u.full_name, u.email,
                   us.tier_code, st.tier_name, us.start_date, us.end_date,
                   us.status, us.created_at, us.updated_at
            from public.user_subscriptions us
            join public.library_users u on u.user_id = us.user_id
            join public.subscription_tiers st on st.tier_code = us.tier_code
        """,
        where_clause=" and ".join(conditions) if conditions else "true",
        order_clause="us.created_at desc, u.email asc",
        params=params,
        limit=limit,
        offset=offset,
        rows_key="subscriptions",
    )


def search_approval_requests(
    *,
    q: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search user approval requests with joined user metadata."""

    conditions: list[str] = []
    params: list[Any] = []
    if _clean(q):
        pattern = f"%{_clean(q)}%"
        conditions.append("(u.full_name ilike %s or u.email ilike %s or coalesce(ar.review_comments, '') ilike %s)")
        params.extend([pattern, pattern, pattern])
    if _clean(status):
        conditions.append("ar.request_status = %s")
        params.append(_clean(status).upper())

    return _search_rows(
        table="user_approval_requests",
        select_sql="""
            select ar.approval_request_id, ar.user_id, u.full_name, u.email,
                   ar.request_status, ar.reviewed_by, ar.reviewed_at,
                   ar.review_comments, ar.created_at, ar.updated_at
            from public.user_approval_requests ar
            join public.library_users u on u.user_id = ar.user_id
        """,
        where_clause=" and ".join(conditions) if conditions else "true",
        order_clause="ar.created_at desc, u.email asc",
        params=params,
        limit=limit,
        offset=offset,
        rows_key="approval_requests",
    )


def _search_rows(
    *,
    table: str,
    select_sql: str,
    where_clause: str,
    order_clause: str,
    params: list[Any],
    limit: int,
    offset: int,
    rows_key: str,
) -> dict[str, Any]:
    count_query = f"select count(*) as total from ({select_sql} where {where_clause}) filtered"
    query = f"{select_sql} where {where_clause} order by {order_clause} limit %s offset %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(count_query, params)
            total = int(cur.fetchone()["total"])
            cur.execute(query, [*params, limit, offset])
            rows = cur.fetchall()
    safe_rows = [_json_safe(row) for row in rows]
    return {
        "table": table,
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(safe_rows),
        rows_key: safe_rows,
        "rows": safe_rows,
    }


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


def _resource_optional_columns() -> set[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'public' and table_name = 'resources'
                """
            )
            return {row["column_name"] for row in cur.fetchall()}


def _catalog_select_sql(optional_columns: set[str]) -> str:
    ingestion_status = "r.ingestion_status" if "ingestion_status" in optional_columns else "null"
    rag_enabled = "r.rag_enabled" if "rag_enabled" in optional_columns else "null"
    metadata_json = "r.metadata_json" if "metadata_json" in optional_columns else "'{}'::jsonb"
    storage_path = "r.storage_path" if "storage_path" in optional_columns else "null"
    return f"""
        select
            r.resource_id,
            r.title,
            r.resource_type,
            r.description,
            r.category_id,
            c.category_name as category,
            r.publisher,
            r.published_date,
            r.language,
            r.isbn,
            r.page_count,
            r.file_url,
            r.preview_file_url,
            r.cover_image_url,
            r.file_name,
            r.file_content_type,
            r.file_size_bytes,
            r.is_premium,
            r.minimum_tier_code,
            r.status,
            r.created_at,
            r.updated_at,
            {ingestion_status} as ingestion_status,
            {rag_enabled} as rag_enabled,
            {metadata_json} as metadata_json,
            {storage_path} as storage_path,
            coalesce((
                select array_agg(a.author_name order by a.author_name)
                from public.resource_authors ra
                join public.authors a on a.author_id = ra.author_id
                where ra.resource_id = r.resource_id
            ), '{{}}') as authors,
            coalesce((
                select array_agg(t.tag_name order by t.tag_name)
                from public.resource_tags rt
                join public.tags t on t.tag_id = rt.tag_id
                where rt.resource_id = r.resource_id
            ), '{{}}') as tags
    """


def _catalog_conditions(
    *,
    q: str | None,
    author: str | None,
    category: str | None,
    tag: str | None,
    publisher: str | None,
    language: str | None,
    tier: str | None,
    status: str | None,
    published_from: str | None,
    published_to: str | None,
) -> tuple[list[str], list[Any]]:
    conditions = []
    params: list[Any] = []

    if _clean(q):
        pattern = f"%{_clean(q)}%"
        conditions.append(
            """
            (
                r.title ilike %s
                or coalesce(r.description, '') ilike %s
                or coalesce(r.publisher, '') ilike %s
                or coalesce(r.isbn, '') ilike %s
                or exists (
                    select 1
                    from public.resource_authors ra
                    join public.authors a on a.author_id = ra.author_id
                    where ra.resource_id = r.resource_id and a.author_name ilike %s
                )
                or exists (
                    select 1
                    from public.resource_tags rt
                    join public.tags t on t.tag_id = rt.tag_id
                    where rt.resource_id = r.resource_id and t.tag_name ilike %s
                )
                or coalesce(c.category_name, '') ilike %s
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern, pattern, pattern, pattern])

    if _clean(author):
        conditions.append(
            """
            exists (
                select 1
                from public.resource_authors ra
                join public.authors a on a.author_id = ra.author_id
                where ra.resource_id = r.resource_id and a.author_name ilike %s
            )
            """
        )
        params.append(f"%{_clean(author)}%")

    if _clean(category):
        conditions.append("c.category_name ilike %s")
        params.append(f"%{_clean(category)}%")

    if _clean(tag):
        conditions.append(
            """
            exists (
                select 1
                from public.resource_tags rt
                join public.tags t on t.tag_id = rt.tag_id
                where rt.resource_id = r.resource_id and t.tag_name ilike %s
            )
            """
        )
        params.append(f"%{_clean(tag)}%")

    if _clean(publisher):
        conditions.append("r.publisher ilike %s")
        params.append(f"%{_clean(publisher)}%")

    if _clean(language):
        conditions.append("r.language ilike %s")
        params.append(f"%{_clean(language)}%")

    if _clean(tier):
        conditions.append("r.minimum_tier_code = %s")
        params.append(_clean(tier).upper())

    if _clean(status):
        conditions.append("r.status = %s")
        params.append(_clean(status).upper())

    if _clean(published_from):
        conditions.append("r.published_date >= %s")
        params.append(_clean(published_from))

    if _clean(published_to):
        conditions.append("r.published_date <= %s")
        params.append(_clean(published_to))

    return conditions, params


def _catalog_order_clause(sort: str) -> str:
    return {
        "title": "r.title asc, r.created_at desc",
        "created_desc": "r.created_at desc, r.title asc",
        "created_asc": "r.created_at asc, r.title asc",
        "published_desc": "r.published_date desc nulls last, r.title asc",
        "published_asc": "r.published_date asc nulls last, r.title asc",
    }.get(sort, "r.title asc, r.created_at desc")


def _catalog_row(row: dict[str, Any]) -> dict[str, Any]:
    data = _json_safe(row)
    data["authors"] = data.get("authors") or []
    data["tags"] = data.get("tags") or []
    data["genre"] = data.get("category")
    return data


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
