
import json
from pathlib import Path

from tools.mcp_client import client


def _resolve_references(value, results):
    """
    Resolve references such as:
    {"$ref": "step_2"}

    References can be nested inside dictionaries or lists.
    """
    if isinstance(value, dict):
        if set(value.keys()) == {"$ref"}:
            step_id = value["$ref"]

            if step_id not in results:
                raise ValueError(
                    f"Result for {step_id} is not available."
                )

            return results[step_id]

        return {
            key: _resolve_references(item, results)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _resolve_references(item, results)
            for item in value
        ]

    return value


def _build_report(goal, results):
    """Build report content from actual successful tool results."""
    sections = [
        "OMNIWEAVE EXECUTION REPORT",
        "=" * 30,
        f"User goal: {goal}",
        "",
        "Results:",
    ]

    for step_id, result in results.items():
        sections.extend([
            "",
            f"{step_id}:",
            json.dumps(result, indent=2, ensure_ascii=False, default=str),
        ])

    return "\n".join(sections)


def execute_plan(plan, tool_client=None):
    """
    Execute a plan sequentially, respecting dependencies.

    Stops after a tool failure. Results from completed steps
    are retained for debugging and reporting.
    """
    tool_client = tool_client or client

    execution = {
        "status": "running",
        "goal": plan.get("goal", ""),
        "step_results": {},
        "errors": [],
        "completed_steps": [],
        "failed_step": None,
        "report_verified": False,
    }

    if plan.get("status") != "ready":
        execution["status"] = "not_started"
        execution["errors"].append(
            f"Plan is not ready: {plan.get('status')}"
        )
        return execution

    steps = plan.get("steps", [])
    known_ids = set()
    seen_ids = set()

    # Validate the entire dependency structure before execution.
    for step in steps:
        step_id = step.get("step_id")
        tool_name = step.get("tool_name")

        if not step_id or step_id in known_ids:
            execution["status"] = "invalid_plan"
            execution["errors"].append(
                f"Missing or duplicate step ID: {step_id}"
            )
            return execution

        if not tool_name:
            execution["status"] = "invalid_plan"
            execution["errors"].append(
                f"Step {step_id} has no tool name."
            )
            return execution

        dependencies = step.get("dependencies", [])

        if not isinstance(dependencies, list):
            execution["status"] = "invalid_plan"
            execution["errors"].append(
                f"Dependencies for {step_id} must be a list."
            )
            return execution

        for dependency in dependencies:
            if dependency not in known_ids:
                execution["status"] = "invalid_plan"
                execution["errors"].append(
                    f"Dependency {dependency} must appear before "
                    f"step {step_id}."
                )
                return execution

        known_ids.add(step_id)

    try:
        available_names = {
            tool["name"] for tool in tool_client.discover_tools()
        }
    except Exception as error:
        execution["status"] = "failed"
        execution["errors"].append(
            f"Could not discover tools: {error}"
        )
        return execution

    # Execute in plan order. The planner must put dependencies first.
    for step in steps:
        step_id = step["step_id"]
        tool_name = step["tool_name"]
        dependencies = step.get("dependencies", [])

        if tool_name not in available_names:
            execution["status"] = "failed"
            execution["failed_step"] = step_id
            execution["errors"].append(
                f"Tool '{tool_name}' is not available."
            )
            break

        if any(
            dependency not in execution["completed_steps"]
            for dependency in dependencies
        ):
            execution["status"] = "failed"
            execution["failed_step"] = step_id
            execution["errors"].append(
                f"Dependencies for {step_id} did not complete."
            )
            break

        try:
            arguments = _resolve_references(
                step.get("arguments", {}),
                execution["step_results"],
            )

            # The old planner uses placeholder report content.
            # Replace it with actual outputs from previous steps.
            if (
                tool_name == "create_report"
                and isinstance(arguments, dict)
                and isinstance(arguments.get("content"), str)
                and arguments["content"].startswith(
                    "Use the outputs of the preceding steps"
                )
            ):
                arguments["content"] = _build_report(
                    execution["goal"],
                    execution["step_results"],
                )

            result = tool_client.call_tool(tool_name, arguments)

            execution["step_results"][step_id] = result
            execution["completed_steps"].append(step_id)

            # Check that the final report can be read and is non-empty.
            if tool_name == "read_saved_report":
                if (
                    not isinstance(result, dict)
                    or not result.get("exists")
                    or not str(result.get("content", "")).strip()
                ):
                    raise ValueError(
                        "The saved report is missing or empty."
                    )

                execution["report_verified"] = True

        except Exception as error:
            execution["status"] = "failed"
            execution["failed_step"] = step_id
            execution["errors"].append(
                f"Step {step_id} ({tool_name}) failed: {error}"
            )
            break

    else:
        execution["status"] = "completed"

    if execution["status"] == "completed":
        report_steps = [
            step for step in steps
            if step.get("tool_name") == "create_report"
        ]

        if report_steps and not execution["report_verified"]:
            execution["status"] = "completed_with_warnings"
            execution["errors"].append(
                "The report was created, but no successful "
                "read-back verification step was completed."
            )

    return execution
