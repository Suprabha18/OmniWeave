
import json
from pathlib import Path
from flask import Blueprint, jsonify, request

from api.schemas import validate_goal_payload
from core.planner import create_plan
from core.orchestrator import Orchestrator
from core.recovery import RecoveryManager
from storage.state_manager import StateManager
from storage.task_repository import TaskRepository
from tools.mcp_client import client
BASE_DIR = Path(__file__).resolve().parents[2]
CSV_PATH = BASE_DIR / "data" / "sales.csv"


tasks_bp = Blueprint("tasks_api", __name__, url_prefix="/api/tasks")

repository = TaskRepository()


def _prepare_plan(plan):
    """Adapt planner step fields to the orchestrator's interface."""
    prepared = dict(plan)
    prepared["steps"] = []

    for original in plan.get("steps", []):
        step = dict(original)
        step["id"] = step.get("step_id")
        step["description"] = step.get(
            "purpose", step.get("step_id", "Execute tool")
        )
        prepared["steps"].append(step)

    return prepared


@tasks_bp.post("")
def create_task():
    payload = request.get_json(silent=True) or {}
    goal, error = validate_goal_payload(payload)

    if error:
        return jsonify({"success": False, "message": error}), 400

    try:
        attachments = payload.get("attachments", [])

        if not attachments and CSV_PATH.is_file():
         attachments = [{
        "name": "sales.csv",
        "path": str(CSV_PATH),
    }]

        if not isinstance(attachments, list):
            return jsonify({
                "success": False,
                "message": "attachments must be a list."
            }), 400

        plan = create_plan(
            goal=goal,
            attachments=attachments,
            available_tools=client.discover_tools()
        )

        if plan.get("status") != "ready":
            return jsonify({
                "success": False,
                "message": "The planner could not create a ready plan.",
                "plan": plan
            }), 400

        plan = _prepare_plan(plan)
        task_id = repository.create_task(plan)

        return jsonify({
            "success": True,
            "task_id": task_id,
            "status": "pending_approval",
            "approval": repository.get_approval(task_id),
            "plan": plan
        }), 201

    except Exception:
        tasks_bp.logger.exception("Task creation failed")
        return jsonify({
            "success": False,
            "message": "Task creation failed. Check the backend logs."
        }), 500


@tasks_bp.get("/<task_id>")
def get_task(task_id):
    try:
        task = repository.get_task(task_id)

        if task is None:
            return jsonify({
                "success": False,
                "message": "Task not found."
            }), 404

        return jsonify({"success": True, "task": task})

    except Exception:
        tasks_bp.logger.exception("Task retrieval failed")
        return jsonify({
            "success": False,
            "message": "Could not retrieve task."
        }), 500


@tasks_bp.post("/<task_id>/execute")
def execute_task(task_id):
    task = repository.get_task(task_id)

    if task is None:
        return jsonify({
            "success": False,
            "message": "Task not found."
        }), 404

    approval = task.get("approval")

    if not approval or approval["status"] != "approved":
        return jsonify({
            "success": False,
            "message": "Task execution requires approval."
        }), 409

    plan = task["plan"]
    tool_results = []

    def invoke_tool(tool_name, arguments):
        arguments = dict(arguments or {})

        if tool_name == "create_report":
            sections = [
                "OMNIWEAVE EXECUTION REPORT",
                "=" * 30,
                f"User goal: {plan['goal']}",
                "",
                "Tool results:"
            ]

            for item in tool_results:
                sections.extend([
                    "",
                    item["tool_name"],
                    json.dumps(
                        item["result"],
                        indent=2,
                        ensure_ascii=False,
                        default=str
                    )
                ])

            arguments["content"] = "\n".join(sections)
            arguments.setdefault(
                "output_path", "output/omniweave_report.txt"
            )

        result = client.call_tool(tool_name, arguments)

        tool_results.append({
            "tool_name": tool_name,
            "result": result
        })

        return result

    try:
        orchestrator = Orchestrator(
            state_manager=repository.state_manager,
            recovery_manager=RecoveryManager(max_retries=2)
        )

        execution = orchestrator.execute_plan(
            plan,
            invoke_tool,
            task_id=task_id
        )

        updated_task = repository.get_task(task_id)

        return jsonify({
            "success": execution.get("status") == "completed",
            "task": updated_task,
            "execution": execution,
            "tool_results": tool_results
        })

    except Exception:
        tasks_bp.logger.exception("Task execution failed")
        return jsonify({
            "success": False,
            "message": "Task execution failed. Check the backend logs."
        }), 500
