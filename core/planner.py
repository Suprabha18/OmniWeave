
"""Main planner for OmniWeave."""

from core.goal_interpreter import interpret_goal
from core.domain_resolver import resolve_domain
from core.intent_resolver import resolve_intent
from core.plan_builder import build_file_workflow
from core.plan_validator import validate_plan as validate_execution_plan
from tools.registry import list_tools


DOMAIN_CUES = {
    "education": (
        "learn", "learning", "study", "course", "courses",
        "college", "colleges", "university", "universities",
        "school", "schools", "scholarship", "scholarships",
        "admission", "degree", "degrees", "student", "students",
        "teach", "tutorial", "exam", "education",
    ),
    "healthcare": (
        "hospital", "hospitals", "clinic", "clinics", "doctor",
        "doctors", "medical", "healthcare", "health care",
        "cardiology", "cardiologist", "cardiac", "appointment",
        "appointments", "patient", "patients", "treatment",
    ),
}

FILE_TASK_CUES = (
    "analyze", "analyse", "analysis", "statistics", "trend",
    "calculate", "csv", "dataset", "comparison",
)


def normalize_tools(tools=None):
    """Discover registered tools or normalize supplied definitions."""

    source = list_tools() if tools is None else tools
    normalized = []

    for tool in source:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue

        normalized.append({
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("input_schema", {}),
            "domains": tool.get("domains", []),
            "intents": tool.get("intents", []),
        })

    return normalized


def find_tool(tools, keywords):
    """Find a tool by its name and description."""

    for tool in tools:
        searchable = (
            tool["name"] + " " + tool["description"]
        ).lower()

        if all(word.lower() in searchable for word in keywords):
            return tool

    return None


def make_step(step_id, tool, arguments, purpose, dependencies=None):
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


def validate_plan(plan, available_tool_names):
    """Keep the existing planner validation interface."""

    tools = [
        {"name": name, "input_schema": {}}
        for name in available_tool_names
    ]

    return validate_execution_plan(plan, tools)


def detect_domain_cues(goal):
    """Identify domain keywords present in a goal."""

    text = goal.lower()

    return [
        domain
        for domain, phrases in DOMAIN_CUES.items()
        if any(phrase in text for phrase in phrases)
    ]


def _base_plan(interpreted):
    """Build the shared plan structure."""

    return {
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
        "validation_errors": [],
        "domain": None,
        "intent": None,
    }


def _route_domain_goal(plan, goal, domain, tools):
    """Classify a domain goal and check registered capabilities."""

    domain_result = resolve_domain(goal)
    plan["domain_result"] = domain_result

    if domain_result.get("status") != "resolved":
        plan["status"] = "needs_clarification"
        plan["clarification_questions"].append(
            domain_result.get(
                "message",
                "Please clarify whether the goal concerns "
                "Education or Healthcare.",
            )
        )
        return plan

    domain = domain_result["domain"]
    plan["domain"] = domain

    intent_result = resolve_intent(goal, domain)
    plan["intent_result"] = intent_result

    if intent_result.get("status") != "resolved":
        plan["status"] = "needs_clarification"
        plan["clarification_questions"].append(
            intent_result.get(
                "message",
                "Please clarify the action you want to perform.",
            )
        )
        return plan

    intent = intent_result["intent"]
    plan["intent"] = intent

    capability_tool = next(
        (
            tool for tool in tools
            if domain in tool.get("domains", [])
            and intent in tool.get("intents", [])
        ),
        None,
    )

    if capability_tool is None:
        plan["status"] = "unsupported"
        plan["errors"].append(
            f"No registered tool supports {domain} / {intent} yet."
        )
        return plan

    plan["status"] = "needs_planning"
    plan["errors"].append(
        f"Tool '{capability_tool['name']}' declares support for "
        f"{domain} / {intent}, but automatic argument construction "
        "for this action is not implemented yet."
    )

    return plan


def create_plan(
    goal,
    input_text=None,
    attachments=None,
    constraints=None,
    available_tools=None,
):
    """
    Interpret a goal, route it, build a workflow, and validate it.
    """

    interpreted = interpret_goal(
        goal=goal,
        input_text=input_text,
        attachments=attachments,
        constraints=constraints,
    )

    plan = _base_plan(interpreted)
    tools = normalize_tools(available_tools)
    tool_names = {tool["name"] for tool in tools}

    if interpreted["status"] == "needs_clarification":
        plan["status"] = "needs_clarification"
        return plan

    goal_text = interpreted["goal"]
    files = interpreted["input_files"]

    # Prefer file planning when the user supplied files and the
    # request explicitly asks to analyze or calculate from them.
    is_file_task = (
        bool(files)
        and any(
            cue in goal_text.lower()
            for cue in FILE_TASK_CUES
        )
    )

    domain_cues = detect_domain_cues(goal_text)

    if domain_cues and not is_file_task:
        plan = _route_domain_goal(
            plan,
            goal_text,
            domain_cues[0],
            tools,
        )
        return plan

    # Use the reusable builder instead of duplicating file workflow
    # construction inside the main planner.
    built_plan = build_file_workflow(
        goal=goal_text,
        input_files=files,
        available_tools=tools,
    )

    plan["steps"] = built_plan.get("steps", [])
    plan["status"] = built_plan.get("status", "needs_planning")
    plan["errors"].extend(built_plan.get("errors", []))
    plan["validation_errors"] = built_plan.get(
        "validation_errors", []
    )

    if plan["status"] == "ready":
        plan["validation_errors"] = validate_execution_plan(
            plan,
            tools,
        )

        if plan["validation_errors"]:
            plan["status"] = "invalid_plan"

    return plan
