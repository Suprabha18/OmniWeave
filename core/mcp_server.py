
"""MCP server exposing OmniWeave's existing demo tools."""

import json
import sys
from pathlib import Path

# Ensure the project root is importable when launched as a subprocess.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP
from tools import demo_tools


mcp = FastMCP("OmniWeave Tools")


def to_json(value):
    """Convert tool results into predictable JSON text."""
    return json.dumps(value, ensure_ascii=False, default=str)


@mcp.tool()
def read_file(file_path: str) -> str:
    """Read a supported CSV or text-based file."""
    return to_json(demo_tools.read_file(file_path))


@mcp.tool()
def analyze_csv(file_path: str) -> str:
    """Analyze a CSV file and calculate numeric statistics."""
    return to_json(demo_tools.analyze_csv(file_path))


@mcp.tool()
def create_report(
    content: str,
    output_path: str = "output/omniweave_report.txt",
) -> str:
    """Save report content inside OmniWeave's output directory."""
    return to_json(demo_tools.create_report(content, output_path))


@mcp.tool()
def read_saved_report(
    file_path: str = "output/omniweave_report.txt",
) -> str:
    """Read a saved report to verify that it exists and has content."""
    return to_json(demo_tools.read_saved_report(file_path))


@mcp.tool()
def simulate_failure() -> str:
    """Intentionally fail to test OmniWeave's error handling."""
    return to_json(demo_tools.simulate_failure())


if __name__ == "__main__":
    mcp.run(transport="stdio")
