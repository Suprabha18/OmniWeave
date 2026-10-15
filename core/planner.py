
from copy import deepcopy
from core.goal_interpreter import interpret_goal


DEFAULT_TOOLS = [
    {
        "name": "read_file",
        "description": "Read text or data from a supported input file.",
        "input_schema": {"file_path": "string"},
    },
    {
        "name": "analyze_csv",
        "description": (
            "Analyze CSV datasets and calculate statistics, "
            "comparisons, and changes."
        ),
        "input_schema": {"file_path": "string"},
    },
    {
        "name": "create_report",
        "description": "Create and save a report to a file.",
        "input_schema": {
            "content": "string",
            "output_path": "string",
        },
    },
    {
        "name": "read_saved_report",
        "description": "Read a previously saved report for verification.",
        "input_schema": {"file_path": "string"},
    },
]


def normalize_tools(tools=None):
    """Return tool descriptions in a consistent format."""
    normalized = []

    for tool in tools if tools is not None else DEFAULT_TOOLS:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue

        normalized.append({
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("input_schema", {}),
        })

    return normalized


def find_tool(tools, keywords):
    """Find a tool using its name and description."""
    for tool in tools:
        searchable_text = (
            tool["name"] + " " + tool["description"]
        ).lower()

        if all(keyword.lower() in searchable_text for keyword in keywords):
            return tool

    return None


def make_step(step_id, tool, arguments, purpose, dependencies=None):
    """Create a step using the shared plan structure."""
    return {
        "step_id": step_id,
        "tool_name": tool["name"],
        "arguments": arguments,
        "purpose": purpose,
        "dependencies": dependencies or [],
        "acceptance_criteria": [
            f"Tool {tool['name']} completes successfully."
        ],
    }


def validate_plan(plan, available_tool_names):
    """Check tool names, step IDs, and dependency references."""
    errors = []
    steps = plan.get("steps", [])
    step_ids = [step["step_id"] for step in steps]

    if len(step_ids) != len(set(step_ids)):
        errors.append("Step IDs must be unique.")

    known_ids = set()

    for step in steps:
        step_id = step.get("step_id")

        if step.get("tool_name") not in available_tool_names:
            errors.append(
                f"Unavailable tool: {step.get('tool_name')}"
            )

        for dependency in step.get("dependencies", []):
            if dependency not in known_ids:
                errors.append(
                    f"Dependency {dependency} must appear "
                    f"before step {step_id}."
                )

        known_ids.add(step_id)

    return errors


def create_plan(
    goal,
    input_text=None,
    attachments=None,
    constraints=None,
    available_tools=None,
):
    """
    Build an execution plan from the goal and available tools.

    This version uses deterministic rules. It does not claim to
    understand or execute tasks for which no suitable tool exists.
    """
    interpreted = interpret_goal(
        goal=goal,
        input_text=input_text,
        attachments=attachments,
        constraints=constraints,
    )

    tools = normalize_tools(available_tools)
    tool_names = {tool["name"] for tool in tools}

    plan = {
        "goal": interpreted["goal"],
        "status": "ready",
        "steps": [],
        "input_text": interpreted["input_text"],
        "input_files": interpreted["input_files"],
        "constraints": interpreted["constraints"],
        "clarification_questions": list(
            interpreted["clarification_questions"]
        ),
        "errors": [],
    }

    if interpreted["status"] == "needs_clarification":
        plan["status"] = "needs_clarification"
        return plan

    goal_text = interpreted["goal"].lower()
    files = interpreted["input_files"]

    wants_report = any(
        word in goal_text
        for word in ("report", "save", "document", "write-up")
    )

    wants_analysis = any(
        word in goal_text
        for word in (
            "analyze", "analyse", "analysis", "calculate",
            "compare", "comparison", "statistics", "trend",
            "decline", "increase", "decrease",
        )
    )

    csv_files = [
        path for path in files
        if path.lower().endswith(".csv")
    ]

    step_number = 1
    source_step_ids = []

    # Read provided files when a suitable reader is available.
    if files:
        reader = find_tool(tools, ["read_file"])

        if reader is None:
            plan["errors"].append(
                "Input files were provided, but no file-reading "
                "tool is available."
            )
        else:
            for file_path in files:
                step_id = f"step_{step_number}"

                plan["steps"].append(make_step(
                    step_id=step_id,
                    tool=reader,
                    arguments={"file_path": file_path},
                    purpose=f"Read input file: {file_path}",
                ))

                source_step_ids.append(step_id)
                step_number += 1

    # Use a CSV analyzer only when CSV analysis is relevant.
    if wants_analysis and csv_files:
        analyzer = find_tool(tools, ["analyze_csv"])

        if analyzer is None:
            plan["errors"].append(
                "CSV analysis was requested, but no suitable "
                "CSV analysis tool is available."
            )
        else:
            for file_path in csv_files:
                step_id = f"step_{step_number}"

                plan["steps"].append(make_step(
                    step_id=step_id,
                    tool=analyzer,
                    arguments={"file_path": file_path},
                    purpose=f"Analyze dataset: {file_path}",
                    dependencies=[
                        source_step_ids[csv_files.index(file_path)]
                    ] if source_step_ids else [],
                ))

                source_step_ids.append(step_id)
                step_number += 1

    # A report can be saved only if a report-writing tool exists.
    if wants_report:
        report_tool = find_tool(tools, ["create_report"])

        if report_tool is None:
            plan["errors"].append(
                "A report was requested, but no report-writing "
                "tool is available."
            )
        else:
            report_id = f"step_{step_number}"

            plan["steps"].append(make_step(
                step_id=report_id,
                tool=report_tool,
                arguments={
                    "content": (
                        "Use the outputs of the preceding steps "
                        "to prepare the requested report."
                    ),
                    "output_path": "output/omniweave_report.txt",
                },
                purpose="Create and save the requested report.",
                dependencies=source_step_ids.copy(),
            ))

            step_number += 1

            verifier = find_tool(tools, ["read_saved_report"])

            if verifier:
                plan["steps"].append(make_step(
                    step_id=f"step_{step_number}",
                    tool=verifier,
                    arguments={
                        "file_path": "output/omniweave_report.txt"
                    },
                    purpose="Verify that the saved report can be read.",
                    dependencies=[report_id],
                ))

    # Prevent an unsupported goal from receiving a false success status.
    if plan["errors"]:
        plan["status"] = "unsupported"
    elif not plan["steps"]:
        plan["status"] = "needs_planning"

    plan["validation_errors"] = validate_plan(
        plan, tool_names
    )

    if plan["validation_errors"]:
        plan["status"] = "invalid_plan"

    return plan
