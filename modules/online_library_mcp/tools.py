from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import OnlineLibraryAPIClient


TABLE_ENDPOINTS: dict[str, str] = {
    "authors": "/authors",
    "categories": "/categories",
    "library_users": "/library-users",
    "reading_progress": "/reading-progress",
    "resource_authors": "/resource-authors",
    "resource_tags": "/resource-tags",
    "resources": "/resources",
    "subscription_rules": "/subscription-rules",
    "subscription_tiers": "/subscription-tiers",
    "tags": "/tags",
    "user_approval_requests": "/user-approval-requests",
    "user_bookshelf": "/user-bookshelf",
    "user_subscriptions": "/user-subscriptions",
}


def register_tools(mcp: FastMCP, api_client: OnlineLibraryAPIClient | None = None) -> None:
    """Register all Online Library MCP tools against a FastMCP server."""

    client = api_client or OnlineLibraryAPIClient()

    async def fetch_table(table_name: str, limit: int, offset: int) -> dict[str, Any]:
        """Validate common pagination and call one table endpoint."""

        if table_name not in TABLE_ENDPOINTS:
            return {
                "error": "unsupported_table",
                "table": table_name,
                "available_tables": sorted(TABLE_ENDPOINTS),
            }
        if limit < 1 or limit > 100:
            return {"error": "invalid_limit", "detail": "limit must be between 1 and 100"}
        if offset < 0:
            return {"error": "invalid_offset", "detail": "offset must be zero or greater"}

        return await client.get_json(TABLE_ENDPOINTS[table_name], {"limit": limit, "offset": offset})

    # FastMCP builds the MCP tool metadata from each decorated function:
    # - tool name: the Python function name, such as get_library_users
    # - tool description: the function docstring below the definition
    # - tool input schema: typed parameters such as limit: int and offset: int
    # The agent sees this metadata through the MCP tools/list request and uses it
    # to choose the best tool for a natural-language user request.
    @mcp.tool()
    async def list_available_tables() -> dict[str, Any]:
        """List all online library data tables exposed as MCP tools. Use this when the user asks what library data, tables, entities, or tool-backed datasets are available."""

        return await client.get_json("/tables")

    @mcp.tool()
    async def get_authors(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List author records for books and library resources. Use this when the user asks for authors, writers, creator names, bios, countries, or active author records."""

        return await fetch_table("authors", limit, offset)

    @mcp.tool()
    async def get_categories(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List library categories, genres, or subject groupings. Use this when the user asks for categories, sections, classifications, genres, or topic buckets."""

        return await fetch_table("categories", limit, offset)

    @mcp.tool()
    async def get_library_users(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List library users, members, patrons, and account records. Use this when the user asks for users, members, registered accounts, approval status, active users, or pending users."""

        return await fetch_table("library_users", limit, offset)

    @mcp.tool()
    async def get_reading_progress(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List user reading progress records. Use this when the user asks about current page, progress percentage, last read time, or how far users have read a resource."""

        return await fetch_table("reading_progress", limit, offset)

    @mcp.tool()
    async def get_resource_authors(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List relationships between resources and authors. Use this when the user asks which authors are linked to which books, documents, or library resources."""

        return await fetch_table("resource_authors", limit, offset)

    @mcp.tool()
    async def get_resource_tags(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List relationships between resources and tags. Use this when the user asks which tags, labels, topics, or keywords are linked to which library resources."""

        return await fetch_table("resource_tags", limit, offset)

    @mcp.tool()
    async def get_resources(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List online library resources such as books, documents, files, and learning materials. Use this when the user asks for books, resources, titles, ISBNs, publishers, premium resources, or available library content."""

        return await fetch_table("resources", limit, offset)

    @mcp.tool()
    async def search_catalog_resources(
        q: str = "",
        author: str = "",
        genre: str = "",
        tag: str = "",
        tier: str = "",
        status: str = "ACTIVE",
        sort: str = "title",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search library catalog resources by title text, author, genre/category, tag, subscription tier, or active status. Use this when the user asks for books by a specific author, title, genre, tag, or filtered catalog search."""

        if limit < 1 or limit > 100:
            return {"error": "invalid_limit", "detail": "limit must be between 1 and 100"}
        if offset < 0:
            return {"error": "invalid_offset", "detail": "offset must be zero or greater"}

        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "sort": sort,
        }
        optional_filters = {
            "q": q,
            "author": author,
            "genre": genre,
            "tag": tag,
            "tier": tier,
            "status": status,
        }
        params.update({key: value for key, value in optional_filters.items() if value})
        return await client.get_json("/catalog/resources", params)

    @mcp.tool()
    async def get_resource_detail(resource_id: str) -> dict[str, Any]:
        """Get detailed catalog metadata for one library resource by resource_id. Use this when the user asks for details about a specific selected resource id."""

        if not resource_id.strip():
            return {"error": "invalid_resource_id", "detail": "resource_id is required"}
        return await client.get_json(f"/catalog/resources/{resource_id.strip()}")

    @mcp.tool()
    async def get_books_by_author(author: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Search books and resources by author name. Use this when the user asks for books by a specific author or writer."""

        if not author.strip():
            return {"error": "invalid_author", "detail": "author is required"}
        if limit < 1 or limit > 100:
            return {"error": "invalid_limit", "detail": "limit must be between 1 and 100"}
        if offset < 0:
            return {"error": "invalid_offset", "detail": "offset must be zero or greater"}
        return await client.get_json("/catalog/books/by-author", {"author": author, "limit": limit, "offset": offset})

    @mcp.tool()
    async def get_books_by_genre(genre: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Search books and resources by genre or category. Use this when the user asks for books in a genre, category, subject, or section."""

        if not genre.strip():
            return {"error": "invalid_genre", "detail": "genre is required"}
        if limit < 1 or limit > 100:
            return {"error": "invalid_limit", "detail": "limit must be between 1 and 100"}
        if offset < 0:
            return {"error": "invalid_offset", "detail": "offset must be zero or greater"}
        return await client.get_json("/catalog/books/by-genre", {"genre": genre, "limit": limit, "offset": offset})

    @mcp.tool()
    async def get_books_by_tag(tag: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Search books and resources by tag, topic, label, or keyword. Use this when the user asks for tagged books or books about a catalog topic."""

        if not tag.strip():
            return {"error": "invalid_tag", "detail": "tag is required"}
        if limit < 1 or limit > 100:
            return {"error": "invalid_limit", "detail": "limit must be between 1 and 100"}
        if offset < 0:
            return {"error": "invalid_offset", "detail": "offset must be zero or greater"}
        return await client.get_json("/catalog/books/by-tag", {"tag": tag, "limit": limit, "offset": offset})

    @mcp.tool()
    async def search_authors(q: str = "", status: str = "ACTIVE", limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Search author lookup records by author name, country, bio, or status. Use this when the user asks to find authors or check if an author exists."""

        return await client.get_json("/catalog/authors", {"q": q, "status": status, "limit": limit, "offset": offset})

    @mcp.tool()
    async def get_available_facets() -> dict[str, Any]:
        """Get available catalog filter values such as authors, genres, categories, tags, languages, and subscription tiers."""

        return await client.get_json("/catalog/facets")

    @mcp.tool()
    async def search_users(
        q: str = "",
        status: str = "",
        approval_status: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search library users by name, email, Keycloak id, account status, or approval status."""

        params = {"q": q, "status": status, "approval_status": approval_status, "limit": limit, "offset": offset}
        return await client.get_json("/users/search", {key: value for key, value in params.items() if value != ""})

    @mcp.tool()
    async def search_subscriptions(
        q: str = "",
        tier: str = "",
        status: str = "",
        user_email: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search user subscription records by user name, email, tier, plan, or subscription status."""

        params = {"q": q, "tier": tier, "status": status, "user_email": user_email, "limit": limit, "offset": offset}
        return await client.get_json("/subscriptions/search", {key: value for key, value in params.items() if value != ""})

    @mcp.tool()
    async def search_approval_requests(
        q: str = "",
        status: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search user approval requests by requester name, email, request status, or review comments."""

        params = {"q": q, "status": status, "limit": limit, "offset": offset}
        return await client.get_json("/approvals/search", {key: value for key, value in params.items() if value != ""})

    @mcp.tool()
    async def get_subscription_rules(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List subscription entitlement rules and limits. Use this when the user asks what a subscription tier allows, what limits apply, or what rules are configured for a tier."""

        return await fetch_table("subscription_rules", limit, offset)

    @mcp.tool()
    async def get_subscription_tiers(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List subscription tiers, plans, levels, and membership options. Use this when the user asks for available plans, tier names, premium levels, free tiers, or subscription descriptions."""

        return await fetch_table("subscription_tiers", limit, offset)

    @mcp.tool()
    async def get_tags(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List tags, labels, keywords, and topics used to classify library resources. Use this when the user asks for available tags, topics, labels, or searchable keywords."""

        return await fetch_table("tags", limit, offset)

    @mcp.tool()
    async def get_user_approval_requests(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List user approval request records. Use this when the user asks for pending approvals, reviewed users, rejected requests, approval workflow status, or admin review queues."""

        return await fetch_table("user_approval_requests", limit, offset)

    @mcp.tool()
    async def get_user_bookshelf(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List user bookshelf and checkout records. Use this when the user asks what users have checked out, saved, added to bookshelf, removed, or currently have in their library."""

        return await fetch_table("user_bookshelf", limit, offset)

    @mcp.tool()
    async def get_user_subscriptions(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List user subscription records. Use this when the user asks which users have which plan, active subscriptions, subscription start dates, end dates, or tier assignments."""

        return await fetch_table("user_subscriptions", limit, offset)
