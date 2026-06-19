from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .tools import register_tools


def create_mcp_server() -> FastMCP:
    """Create the Streamable HTTP MCP server for Online Library tools."""

    config = load_config()
    mcp = FastMCP(
        "OnlineLibraryMCP",
        host=config.host,
        port=config.port,
        streamable_http_path="/mcp",
        # Stateless JSON responses keep this on the current Streamable HTTP path
        # without using the deprecated HTTP+SSE transport or SSE response streams.
        stateless_http=True,
        json_response=True,
    )
    register_tools(mcp)
    return mcp


def main() -> None:
    """Run the MCP server using the current Streamable HTTP transport."""

    mcp = create_mcp_server()
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
