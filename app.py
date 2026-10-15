
from pathlib import Path
import json

from api.main import register_api


from flask import Flask, jsonify, request, send_from_directory

from core.planner import create_plan
from core.orchestrator import Orchestrator
from core.recovery import RecoveryManager
from storage.state_manager import StateManager
from tools.mcp_client import client

BASE_DIR = Path(__file__).resolve().parent
REPORT_PATH = BASE_DIR / "output" / "omniweave_report.txt"
CSV_PATH = BASE_DIR / "data" / "sales.csv"

app = Flask(__name__, static_folder=None)
register_api(app)


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "status": "online",
        "dataset_available": CSV_PATH.is_file(),
        "report_available": REPORT_PATH.is_file(),
    })


@app.get("/api/report")
def get_report():
    if not REPORT_PATH.is_file():
        return jsonify({
            "success": False,
            "message": "No report has been generated yet.",
        }), 404

    return jsonify({
        "success": True,
        "report": REPORT_PATH.read_text(encoding="utf-8"),
    })


@app.post("/api/run")
def run_workflow():
    payload = request.get_json(silent=True) or {}
    goal = str(payload.get("goal", "")).strip()

    if not goal:
        return jsonify({
            "success": False,
            "message": "Please enter a goal.",
        }), 400

    if not CSV_PATH.is_file():
        return jsonify({
            "success": False,
            "message": "Dataset not found at data/sales.csv.",
        }), 400

    events = []
    tool_results = []

    try:
        plan = create_plan(
            goal=goal,
            attachments=[{
                "name": "sales.csv",
                "path": str(CSV_PATH),
            }],
        )

        if plan.get("status") != "ready":
            return jsonify({
                "success": False,
                "message": "The planner could not create a valid plan.",
                "plan": plan,
            }), 400

        # Adapt planner steps to the orchestrator's expected format.
        integrated_plan = dict(plan)
        integrated_plan["steps"] = []

        for original in plan.get("steps", []):
            step = dict(original)
            step["id"] = step.get("step_id")
            step["description"] = step.get(
                "purpose", step.get("step_id", "Execute tool")
            )
            integrated_plan["steps"].append(step)

        def build_report():
            sections = [
                "OMNIWEAVE EXECUTION REPORT",
                "=" * 30,
                f"User goal: {goal}",
                "",
                "Executed tool results:",
            ]

            for index, item in enumerate(tool_results, start=1):
                sections.extend([
                    "",
                    f"{index}. {item['tool_name']}",
                    json.dumps(
                        item["result"],
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    ),
                ])

            return "\n".join(sections)

        def invoke_tool(tool_name, arguments):
            arguments = dict(arguments or {})

            if tool_name == "create_report":
                arguments["content"] = build_report()
                arguments.setdefault(
                    "output_path", "output/omniweave_report.txt"
                )

            result = client.call_tool(tool_name, arguments)

            tool_results.append({
                "tool_name": tool_name,
                "result": result,
            })

            return result

        def record_event(**event):
            events.append(event)

        orchestrator = Orchestrator(
            state_manager=StateManager(),
            recovery_manager=RecoveryManager(max_retries=2),
        )

        result = orchestrator.execute_plan(
            integrated_plan,
            invoke_tool,
            event_callback=record_event,
        )

        report = ""
        if REPORT_PATH.is_file():
            report = REPORT_PATH.read_text(encoding="utf-8")

        verified = (
            result.get("status") == "completed"
            and bool(report.strip())
            and goal in report
        )

        return jsonify({
            "success": verified,
            "goal": goal,
            "plan": plan,
            "execution": result,
            "events": events,
            "tool_results": tool_results,
            "report": report,
            "report_verified": verified,
        })

    except Exception as exc:
        app.logger.exception("Workflow execution failed")
        return jsonify({
            "success": False,
            "message": str(exc),
            "events": events,
        }), 500


# Serve the existing dashboard's CSS and JavaScript.
@app.get("/<path:filename>")
def static_files(filename):
    allowed = {"index.html", "style.css", "script.js"}
    if filename not in allowed:
        return jsonify({"message": "Not found"}), 404
    return send_from_directory(BASE_DIR, filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
