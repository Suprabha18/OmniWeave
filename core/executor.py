import json

from tools.registry import execute_tool


def _resolve_references(value, results):
    """Resolve references such as {'$ref': 'step_1'} recursively."""

    if isinstance(value, dict):
        if set(value.keys()) == {"$ref"}:
            ref = value["$ref"]

            if ref not in results:
                raise ValueError(
                    f"Reference '{ref}' has no successful result."
                )

            return results[ref]

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


def _call_tool(tool_name, arguments, tool_client=None):
    """Support both the test client and the local tool registry."""

    if tool_client is not None:
        return tool_client.call_tool(tool_name, arguments)

    return execute_tool(tool_name, arguments)


def execute_plan(plan, tool_client=None):
    """Execute a plan and return structured execution details."""

    steps = plan.get("steps", [])

    if plan.get("status") != "ready":
        return {
            "status": "not_started",
            "message": "The plan is not ready for execution.",
            "completed_steps": [],
            "step_results": [],
            "results": {},
            "errors": [],
            "failed_step": None,
            "skipped_steps": [],
            "report_verified": False,
            "verified": False,
        }

    step_ids = [step.get("step_id") for step in steps]

    if len(step_ids) != len(set(step_ids)):
        return {
            "status": "failed",
            "message": "The plan contains duplicate step IDs.",
            "completed_steps": [],
            "step_results": [],
            "results": {},
            "errors": ["The plan contains duplicate step IDs."],
            "failed_step": None,
            "skipped_steps": [],
            "report_verified": False,
            "verified": False,
        }

    results = {}
    step_results = []
    completed_steps = []
    errors = []
    skipped_steps = []
    failed_step = None

    for index, step in enumerate(steps):
        step_id = step.get("step_id")
        tool_name = step.get("tool_name")
        dependencies = step.get("dependencies", [])

        missing_dependencies = [
            dependency
            for dependency in dependencies
            if dependency not in results
        ]

        if missing_dependencies:
            error_message = (
                "Dependencies did not complete successfully: "
                + ", ".join(missing_dependencies)
            )

            skipped_steps.append(step_id)
            step_results.append({
                "step_id": step_id,
                "tool_name": tool_name,
                "status": "skipped",
                "error": error_message,
            })

            errors.append({
                "step_id": step_id,
                "error": error_message,
            })

            # Do not execute dependent or later steps.
            for remaining_step in steps[index + 1:]:
                remaining_id = remaining_step.get("step_id")
                skipped_steps.append(remaining_id)

                step_results.append({
                    "step_id": remaining_id,
                    "tool_name": remaining_step.get("tool_name"),
                    "status": "skipped",
                    "error": (
                        "Not executed because an earlier step "
                        "failed or was skipped."
                    ),
                })

            break

        try:
            arguments = _resolve_references(
                step.get("arguments", {}),
                results,
            )

            # Include actual earlier results in the generated report.
            if (
                tool_name == "create_report"
                and isinstance(arguments, dict)
                and isinstance(arguments.get("content"), str)
                and "preceding steps" in arguments["content"].lower()
            ):
                arguments["content"] = (
                    "OmniWeave Execution Report\n\n"
                    + json.dumps(results, indent=2, default=str)
                )

            output = _call_tool(
                tool_name,
                arguments,
                tool_client,
            )

            if isinstance(output, dict) and output.get("success") is False:
                raise RuntimeError(
                    output.get("error", "The tool reported failure.")
                )

            results[step_id] = output
            completed_steps.append(step_id)

            step_results.append({
                "step_id": step_id,
                "tool_name": tool_name,
                "status": "success",
                "output": output,
            })

        except Exception as exc:
            failed_step = step_id
            error_message = str(exc)

            errors.append({
                "step_id": step_id,
                "error": error_message,
            })

            step_results.append({
                "step_id": step_id,
                "tool_name": tool_name,
                "status": "failed",
                "error": error_message,
            })

            for remaining_step in steps[index + 1:]:
                remaining_id = remaining_step.get("step_id")
                skipped_steps.append(remaining_id)

                step_results.append({
                    "step_id": remaining_id,
                    "tool_name": remaining_step.get("tool_name"),
                    "status": "skipped",
                    "error": (
                        "Not executed because an earlier step failed."
                    ),
                })

            break

    all_successful = (
        len(completed_steps) == len(steps)
        and not errors
    )

    report_read_results = [
        item["output"]
        for item in step_results
        if (
            item["tool_name"] == "read_saved_report"
            and item["status"] == "success"
        )
    ]

    report_verified = (
        all_successful
        and bool(report_read_results)
        and all(
            isinstance(output, dict)
            and output.get("success") is True
            and output.get("exists") is True
            for output in report_read_results
        )
    )

    return {
        "status": "completed" if all_successful else "failed",
        "message": (
            "All plan steps completed."
            if all_successful
            else "Execution stopped because a step failed or was skipped."
        ),
        "completed_steps": completed_steps,
        "step_results": step_results,
        "results": results,
        "errors": errors,
        "failed_step": failed_step,
        "skipped_steps": skipped_steps,
        "report_verified": report_verified,
        "verified": report_verified,
    }
