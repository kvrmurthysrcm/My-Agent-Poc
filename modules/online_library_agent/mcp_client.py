from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .config import AgentConfig, load_config


@dataclass(frozen=True, slots=True)
class ToolInfo:
    """Agent-friendly copy of MCP tool metadata."""

    name: str
    description: str
    input_schema: dict[str, Any]


class OnlineLibraryMCPClient:
    """MCP Streamable HTTP client for Online Library tools."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or load_config()

    async def list_tools(self) -> list[ToolInfo]:
        """Open an MCP session, initialize it, and read tool metadata."""

        async with streamablehttp_client(self.config.mcp_url, timeout=self.config.timeout_seconds) as (
            read_stream,
            write_stream,
            _get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
                return [
                    ToolInfo(
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=dict(tool.inputSchema or {}),
                    )
                    for tool in result.tools
                ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call one MCP tool and parse the JSON text result returned by FastMCP."""

        async with streamablehttp_client(self.config.mcp_url, timeout=self.config.timeout_seconds) as (
            read_stream,
            write_stream,
            _get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

        if result.isError:
            return {"error": "mcp_tool_error", "tool": tool_name, "content": [str(item) for item in result.content]}
        if not result.content:
            return {"error": "mcp_empty_tool_result", "tool": tool_name}

        first_item = result.content[0]
        text = getattr(first_item, "text", str(first_item))
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"tool": tool_name, "text": text}
        return parsed if isinstance(parsed, dict) else {"tool": tool_name, "result": parsed}
