
def validate_plan(plan, available_tools):
    """
    Validate a plan before execution.

    available_tools may be a list of tool definitions returned
    by tools.registry.list_tools().
    """

    errors = []

    if not isinstance(plan, dict):
        return ["Plan must be a dictionary."]

    if plan.get("status") != "ready":
        errors.append(
            "Only plans with status 'ready' can be validated for execution."
        )

    steps = plan.get("steps")

    if not isinstance(steps, list):
        return errors + ["Plan steps must be a list."]

    if not steps:
        errors.append("Plan must contain at least one step.")
        return errors

    tool_map = {
        tool["name"]: tool
        for tool in available_tools
        if isinstance(tool, dict) and tool.get("name")
    }

    step_ids = []

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"Step at index {index} must be a dictionary.")
            continue

        step_id = step.get("step_id")
        tool_name = step.get("tool_name")
        arguments = step.get("arguments", {})
        dependencies = step.get("dependencies", [])

        if not isinstance(step_id, str) or not step_id.strip():
            errors.append(f"Step at index {index} has an invalid step ID.")
        else:
            step_ids.append(step_id)

        if not isinstance(tool_name, str) or tool_name not in tool_map:
            errors.append(
                f"Step {step_id} references unavailable tool '{tool_name}'."
            )
            continue

        if not isinstance(arguments, dict):
            errors.append(
                f"Arguments for step {step_id} must be a dictionary."
            )
            continue

        if not isinstance(dependencies, list):
            errors.append(
                f"Dependencies for step {step_id} must be a list."
            )
            continue

        schema = tool_map[tool_name].get("input_schema", {})

        if isinstance(schema, dict):
            for argument_name in schema:
                if argument_name not in arguments:
                    errors.append(
                        f"Step {step_id} is missing argument "
                        f"'{argument_name}'."
                    )

    if len(step_ids) != len(set(step_ids)):
        errors.append("Step IDs must be unique.")

    seen_ids = set()

    for step in steps:
        if not isinstance(step, dict):
            continue

        step_id = step.get("step_id")
        dependencies = step.get("dependencies", [])

        if not isinstance(dependencies, list):
            continue

        for dependency in dependencies:
            if dependency not in seen_ids:
                errors.append(
                    f"Step {step_id} depends on '{dependency}', "
                    "which must be a preceding step."
                )

        if step_id:
            seen_ids.add(step_id)

    return errors
