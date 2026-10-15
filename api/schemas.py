
def validate_goal_payload(payload):
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object."

    goal = payload.get("goal")

    if not isinstance(goal, str) or not goal.strip():
        return None, "A non-empty goal is required."

    goal = goal.strip()

    if len(goal) > 2000:
        return None, "Goal must be 2000 characters or fewer."

    return goal, None


def validate_approval_payload(payload):
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object."

    action = payload.get("action")

    if action not in ("approve", "reject"):
        return None, "Action must be 'approve' or 'reject'."

    reason = payload.get("reason", "")

    if not isinstance(reason, str) or len(reason) > 1000:
        return None, "Reason must be a string of at most 1000 characters."

    return {"action": action, "reason": reason.strip()}, None
