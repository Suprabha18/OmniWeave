
from tools import demo_tools


TOOL_REGISTRY = {
    "read_file": {
        "function": demo_tools.read_file,
        "description": "Read a supported CSV or text-based input file.",
        "input_schema": {
            "file_path": "string",
        },
    },
    "analyze_csv": {
        "function": demo_tools.analyze_csv,
        "description": (
            "Analyze a CSV dataset and calculate numeric statistics."
        ),
        "input_schema": {
            "file_path": "string",
        },
    },
    "create_report": {
        "function": demo_tools.create_report,
        "description": "Save report content to a file in the output folder.",
        "input_schema": {
            "content": "any",
            "output_path": "string",
        },
    },
    "read_saved_report": {
        "function": demo_tools.read_saved_report,
        "description": "Read a saved report to verify its contents.",
        "input_schema": {
            "file_path": "string",
        },
    },
    "simulate_failure": {
        "function": demo_tools.simulate_failure,
        "description": "Intentionally fail to test error recovery.",
        "input_schema": {},
    },
}


def list_tools():
    """Return tool descriptions without exposing Python functions."""

    return [
        {
            "name": name,
            "description": details["description"],
            "input_schema": details["input_schema"],
        }
        for name, details in TOOL_REGISTRY.items()
    ]


def get_tool(tool_name):
    """Return a registered tool or raise an informative error."""

    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"Unknown tool: {tool_name}")

    return TOOL_REGISTRY[tool_name]


def execute_tool(tool_name, arguments=None):
    """Execute a registered tool with the supplied arguments."""

    tool = get_tool(tool_name)
    arguments = arguments or {}

    if not isinstance(arguments, dict):
        raise TypeError("Tool arguments must be provided as a dictionary.")

    function = tool["function"]
    return function(**arguments)
