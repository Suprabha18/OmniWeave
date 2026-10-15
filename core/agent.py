
from core.planner import create_plan
from core.executor import execute_plan


def run_agent(
    goal,
    input_text=None,
    attachments=None,
    constraints=None,
    max_iterations=3,
):
    """
    Orchestrate planning and execution with bounded retries.

    Retries are limited to execution attempts. This version does
    not yet generate a different plan automatically.
    """

    if not isinstance(goal, str) or not goal.strip():
        return {
            "status": "needs_clarification",
            "goal": goal,
            "message": "Please provide a goal for OmniWeave.",
            "plan": None,
            "execution": None,
            "attempts": 0,
        }

    plan = create_plan(
        goal=goal,
        input_text=input_text,
        attachments=attachments,
        constraints=constraints,
    )

    if plan.get("status") != "ready":
        return {
            "status": plan.get("status", "planning_failed"),
            "goal": goal,
            "message": (
                "The goal could not be executed. Check the plan "
                "status, errors, or clarification questions."
            ),
            "plan": plan,
            "execution": None,
            "attempts": 0,
        }

    max_iterations = max(1, min(int(max_iterations), 3))
    execution = None
    history = []

    for attempt in range(1, max_iterations + 1):
        try:
            execution = execute_plan(plan)
        except Exception as exc:
            execution = {
                "status": "failed",
                "error": str(exc),
            }

        history.append({
            "attempt": attempt,
            "result": execution,
        })

        # Do not assume success if the executor's result is unclear.
        if not isinstance(execution, dict):
            break

        status = str(execution.get("status", "")).lower()

        if status in {"success", "completed", "verified"}:
            return {
                "status": "completed",
                "goal": goal,
                "message": "Execution reported completion.",
                "plan": plan,
                "execution": execution,
                "attempts": attempt,
                "history": history,
            }

        # Do not blindly rerun an execution with an unclear outcome.
        if status not in {"failed", "error"}:
            break

    return {
        "status": "failed",
        "goal": goal,
        "message": (
            "Execution did not report confirmed completion. "
            "Review the execution output before retrying manually."
        ),
        "plan": plan,
        "execution": execution,
        "attempts": len(history),
        "history": history,
    }
