
from storage.state_manager import StateManager
from core.recovery import RecoveryManager


class Orchestrator:
    def __init__(self, state_manager=None, recovery_manager=None):
        self.state_manager = state_manager or StateManager()
        self.recovery_manager = recovery_manager or RecoveryManager()

    def _emit(
        self,
        callback,
        task_id,
        step_id,
        status,
        message,
        **extra
    ):
        self.state_manager.audit(
            task_id,
            step_id,
            status,
            message,
            extra or None
        )

        if callback:
            try:
                callback(
                    task_id=task_id,
                    step_id=step_id,
                    status=status,
                    message=message,
                    **extra
                )
            except Exception:
                # A dashboard callback must not corrupt execution state.
                pass

    def _normalize_result(self, result):
        if not isinstance(result, dict):
            return {
                "success": False,
                "error": "Tool returned a non-dictionary result",
                "retryable": False
            }

        if result.get("success") is True:
            return result

        normalized = dict(result)
        normalized["success"] = False
        normalized.setdefault("error", "Tool operation failed")
        normalized.setdefault("retryable", True)
        return normalized

    def execute_plan(
        self,
        plan,
        invoke_tool,
        task_id=None,
        event_callback=None
    ):
        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("Plan steps must be a list")

        # Validate the plan before creating or modifying persistent state.
        step_ids = [step.get("id") for step in steps]

        if any(not step_id for step_id in step_ids):
            raise ValueError("Every step must have an id")

        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Step IDs must be unique")

        known_ids = set(step_ids)

        for step in steps:
            if not step.get("tool_name"):
                raise ValueError(
                    f"Missing tool_name for step {step['id']}"
                )

            if not isinstance(step.get("arguments", {}), dict):
                raise ValueError(
                    f"Arguments must be a dictionary: {step['id']}"
                )

            for dependency in step.get("dependencies", []):
                if dependency not in known_ids:
                    raise ValueError(
                        f"Unknown dependency {dependency} "
                        f"for step {step['id']}"
                    )

                if dependency == step["id"]:
                    raise ValueError(
                        f"A step cannot depend on itself: {step['id']}"
                    )

        # Check for dependency cycles.
        graph = {
            step["id"]: step.get("dependencies", [])
            for step in steps
        }
        visited = set()
        visiting = set()

        def visit(step_id):
            if step_id in visiting:
                raise ValueError("Plan contains a dependency cycle")

            if step_id in visited:
                return

            visiting.add(step_id)
            for dependency in graph[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in graph:
            visit(step_id)

        # A new task is created once. Existing tasks retain their saved plan.
        if task_id is None:
            task_id = self.state_manager.create_task(plan)
        else:
            existing = self.state_manager.get_task(task_id)
            if existing is None:
                raise ValueError(f"Task not found: {task_id}")

            saved_plan = existing["plan"]
            if saved_plan != plan:
                raise ValueError(
                    "The supplied plan differs from the saved task plan"
                )

        completed = self.state_manager.get_completed_step_ids(task_id)
        saved_steps = {
            step["step_id"]: step
            for step in self.state_manager.get_steps(task_id)
        }

        # Verify dependencies of previously completed steps too.
        for step in steps:
            if step["id"] in completed:
                missing = set(step.get("dependencies", [])) - completed
                if missing:
                    self.state_manager.set_task_status(
                        task_id,
                        "failed",
                        f"Completed step has incomplete dependencies: "
                        f"{sorted(missing)}"
                    )
                    return {
                        "task_id": task_id,
                        "status": "failed",
                        "error": "Persistent state has inconsistent dependencies",
                        "steps": self.state_manager.get_steps(task_id)
                    }

        self.state_manager.set_task_status(task_id, "running")
        self._emit(
            event_callback, task_id, None, "running",
            "Task execution started"
        )

        # Process steps in dependency order, even if the plan is not sorted.
        pending = [step for step in steps if step["id"] not in completed]
        failures = []

        while pending:
            ready = [
                step for step in pending
                if set(step.get("dependencies", [])) <= completed
            ]

            if not ready:
                # Dependencies cannot be satisfied, so don't run blocked steps.
                blocked_ids = {step["id"] for step in pending}
                for step in pending:
                    self.state_manager.update_step(
                        task_id,
                        step["id"],
                        "blocked",
                        error="Dependencies failed or could not be completed"
                    )
                    self._emit(
                        event_callback,
                        task_id,
                        step["id"],
                        "blocked",
                        "Step blocked by incomplete dependencies"
                    )

                failures.append({
                    "error": "Unresolved dependencies",
                    "blocked_steps": sorted(blocked_ids)
                })
                break

            for step in ready:
                pending.remove(step)
                step_id = step["id"]
                tool_name = step["tool_name"]
                arguments = step.get("arguments", {})
                prior = saved_steps.get(step_id, {})
                attempts = int(prior.get("attempts") or 0)

                self.state_manager.update_step(
                    task_id, step_id, "running", attempts=attempts
                )
                self._emit(
                    event_callback, task_id, step_id, "running",
                    f"Executing {tool_name}"
                )

                final_result = None

                while True:
                    attempts += 1

                    try:
                        raw_result = invoke_tool(tool_name, arguments)
                        result = self._normalize_result(raw_result)
                    except Exception as exc:
                     result = self.recovery_manager.classify_exception(exc)

                    self.state_manager.record_tool_call(
                        task_id,
                        step_id,
                        tool_name,
                        attempts,
                        arguments,
                        result
                    )

                    if result.get("success"):
                        final_result = result
                        break

                    action = self.recovery_manager.next_action(
                        result, attempts - (prior.get("attempts") or 0)
                    )

                    if action != "retry":
                        final_result = result
                        break

                    self.state_manager.update_step(
                        task_id,
                        step_id,
                        "retrying",
                        attempts=attempts,
                        error=result.get("error")
                    )
                    self._emit(
                        event_callback, task_id, step_id, "retrying",
                        f"Retrying after failure: {result.get('error')}",
                        attempt=attempts
                    )

                if final_result and final_result.get("success"):
                    self.state_manager.update_step(
                        task_id,
                        step_id,
                        "completed",
                        attempts=attempts,
                        result=final_result
                    )
                    completed.add(step_id)

                    self.state_manager.save_checkpoint(
                        task_id,
                        step_id,
                        {
                            "completed_step_ids": sorted(completed),
                            "result": final_result
                        }
                    )

                    source = (
                        final_result.get("source")
                        if final_result else None
                    ) or ("mcp" if tool_name.startswith("mcp__") else "local")

                    self._emit(
                        event_callback, task_id, step_id, "completed",
                        f"Step completed: {step.get('description', step_id)}",
                        result=final_result,
                        source=source,
                        mcp_server=(
                            final_result.get("mcp_server")
                            if final_result else None
                        ),
                    )
                
                else:
                    error = (
                        final_result.get("error", "Unknown failure")
                        if final_result else "No result returned"
                    )
                    suggestion = (
                        final_result.get("recovery_suggestion")
                        if final_result else None
                    )

                    self.state_manager.update_step(
                        task_id,
                        step_id,
                        "failed",
                        attempts=attempts,
                        result=final_result,
                        error=error
                    )
                    failure = {
                        "step_id": step_id,
                        "tool_name": tool_name,
                        "error": error,
                        "attempts": attempts,
                        "retryable": (
                            final_result.get("retryable", False)
                            if final_result else False
                        ),
                        "recovery_suggestion": suggestion,
                    }
                    failures.append(failure)

                    source = (
                        final_result.get("source")
                        if final_result else None
                    ) or ("mcp" if tool_name.startswith("mcp__") else "local")

                    self._emit(
                        event_callback,
                        task_id,
                        step_id,
                        "failed",
                        f"Step failed: {error}",
                        recovery_suggestion=suggestion,
                        attempts=attempts,
                        source=source,
                        mcp_server=(
                            final_result.get("mcp_server")
                            if final_result else None
                        ),
                    )

        status = "completed" if not failures else "failed"
        error = None if not failures else str(failures)

        self.state_manager.set_task_status(task_id, status, error)
        self._emit(
            event_callback,
            task_id,
            None,
            status,
            "Task completed successfully"
            if status == "completed"
            else "Task execution failed",
            errors=failures
        )

        return {
            "task_id": task_id,
            "status": status,
            "completed_step_ids": sorted(completed),
            "failures": failures,
            "steps": self.state_manager.get_steps(task_id),
            "events": self.state_manager.get_events(task_id)
        }
