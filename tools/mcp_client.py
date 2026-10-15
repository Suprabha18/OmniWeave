
from tools.registry import list_tools, execute_tool


class MCPClient:
    """
    Local tool-client interface.

    This version calls registered Python tools directly.
    It is not yet a network connection to an MCP server.
    """

    def discover_tools(self):
        """Return the tools currently available to OmniWeave."""
        return list_tools()

    def call_tool(self, tool_name, arguments=None):
        """Call a tool and return its result."""
        return execute_tool(tool_name, arguments)


# Convenient shared client for local development.
client = MCPClient()
