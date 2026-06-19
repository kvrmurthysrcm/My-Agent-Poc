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
