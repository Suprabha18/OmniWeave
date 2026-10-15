
"""Synchronous interface for OmniWeave's real MCP client."""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PATH = Path(__file__).with_name("mcp_server.py").resolve()


class MCPClient:
    """Connect to the local OmniWeave MCP server over stdio."""

    def __init__(self, server_path=SERVER_PATH):
        self.server_path = Path(server_path).resolve()

    async def _connect(self):
        """Open and initialize an MCP session."""
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(self.server_path)],
        )

        transport = stdio_client(parameters)
        return transport

    async def _discover_tools(self):
        async with await self._connect() as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.list_tools()

                tools = []
                for tool in response.tools:
                    schema_data = tool.model_dump(by_alias=True)
                    input_schema = schema_data.get(
                        "inputSchema",
                        schema_data.get("input_schema", {}),
                    )
                    properties = input_schema.get("properties", {})

                    tools.append({
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": {
                            name: details.get("type", "any")
                            for name, details in properties.items()
                        },
                    })

                return tools

    async def _call_tool(self, tool_name, arguments):
        async with await self._connect() as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    tool_name,
                    arguments=arguments,
                )

                result_data = result.model_dump(by_alias=True)
                if result_data.get("isError", result_data.get("is_error", False)):
                    messages = [
                        item.text
                        for item in result.content
                        if hasattr(item, "text")
                    ]
                    raise RuntimeError(
                        "; ".join(messages) or f"MCP tool failed: {tool_name}"
                    )

                messages = [
                    item.text
                    for item in result.content
                    if hasattr(item, "text")
                ]

                if len(messages) == 1:
                    try:
                        return json.loads(messages[0])
                    except json.JSONDecodeError:
                        return messages[0]

                return messages

    def discover_tools(self):
        """Return tools discovered from the running MCP server."""
        return asyncio.run(self._discover_tools())

    def call_tool(self, tool_name, arguments=None):
        """Invoke a tool through the MCP protocol."""
        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise TypeError("Tool arguments must be a dictionary.")

        return asyncio.run(self._call_tool(tool_name, arguments))


# Shared client used by the executor.
client = MCPClient()
