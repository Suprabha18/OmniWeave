
"""Build and validate multi-step plans from tool definitions."""

from core.plan_validator import validate_plan


def _find_tool(tools, name):
    """Return a tool definition by name."""

    for tool in tools:
        if tool.get("name") == name:
            return tool

    return None


def _make_step(step_id, tool, arguments, purpose, dependencies=None):
    """Create a consistently structured plan step."""

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


def build_file_workflow(goal, input_files, available_tools):
    """
    Construct a file workflow using the registered tools.

    Supports reading supplied files, analyzing CSV files,
    creating reports, and verifying saved reports.
    """

    if not isinstance(goal, str) or not goal.strip():
        return {
            "status": "needs_clarification",
            "steps": [],
            "errors": ["A non-empty goal is required."],
            "validation_errors": [],
        }

    if not isinstance(input_files, list):
        return {
            "status": "invalid_plan",
            "steps": [],
            "errors": ["input_files must be a list."],
            "validation_errors": [],
        }

    tools = [
        tool for tool in available_tools
        if isinstance(tool, dict) and tool.get("name")
    ]

    goal_lower = goal.lower()

    wants_analysis = any(
        phrase in goal_lower
        for phrase in (
            "analyze", "analyse", "analysis", "calculate",
            "compare", "comparison", "statistics", "trend",
            "increase", "decrease", "decline",
        )
    )

    wants_report = any(
        phrase in goal_lower
        for phrase in ("report", "save", "document", "write-up")
    )

    csv_files = [
        path for path in input_files
        if isinstance(path, str) and path.lower().endswith(".csv")
    ]

    steps = []
    errors = []
    read_steps = {}
    analysis_steps = []
    next_number = 1

    # Step A: Read the provided files.
    if input_files:
        reader = _find_tool(tools, "read_file")

        if reader is None:
            errors.append("No registered read_file tool is available.")
        else:
            for path in input_files:
                if not isinstance(path, str) or not path.strip():
                    errors.append("An input file path is invalid.")
                    continue

                step_id = f"step_{next_number}"

                steps.append(_make_step(
                    step_id,
                    reader,
                    {"file_path": path},
                    f"Read input file: {path}",
                ))

                read_steps[path] = step_id
                next_number += 1

    # Step B: Analyze each supplied CSV file.
    if wants_analysis:
        if not csv_files:
            errors.append(
                "Analysis was requested, but no CSV input file was supplied."
            )
        else:
            analyzer = _find_tool(tools, "analyze_csv")

            if analyzer is None:
                errors.append("No registered analyze_csv tool is available.")
            else:
                for path in csv_files:
                    step_id = f"step_{next_number}"
                    dependencies = []

                    if path in read_steps:
                        dependencies.append(read_steps[path])

                    steps.append(_make_step(
                        step_id,
                        analyzer,
                        {"file_path": path},
                        f"Analyze CSV dataset: {path}",
                        dependencies,
                    ))

                    analysis_steps.append(step_id)
                    next_number += 1

    # Step C: Create the report from the preceding results.
    report_id = None

    if wants_report:
        report_tool = _find_tool(tools, "create_report")

        if report_tool is None:
            errors.append("No registered create_report tool is available.")
        else:
            report_id = f"step_{next_number}"

            dependencies = (
                analysis_steps
                if analysis_steps
                else list(read_steps.values())
            )

            steps.append(_make_step(
                report_id,
                report_tool,
                {
                    "content": (
                        "Use the outputs of the preceding steps "
                        "to prepare the requested report."
                    ),
                    "output_path": "output/omniweave_report.txt",
                },
                "Create a report from the available results.",
                dependencies,
            ))

            next_number += 1

            # Step D: Verify the saved report.
            verifier = _find_tool(tools, "read_saved_report")

            if verifier is not None:
                steps.append(_make_step(
                    f"step_{next_number}",
                    verifier,
                    {"file_path": "output/omniweave_report.txt"},
                    "Verify that the report was saved and can be read.",
                    [report_id],
                ))

    if errors:
        status = "unsupported"
    elif not steps:
        status = "needs_planning"
    else:
        status = "ready"

    plan = {
        "goal": goal,
        "status": status,
        "steps": steps,
        "errors": errors,
        "validation_errors": [],
    }

    if status == "ready":
        plan["validation_errors"] = validate_plan(plan, tools)

        if plan["validation_errors"]:
            plan["status"] = "invalid_plan"

    return plan
