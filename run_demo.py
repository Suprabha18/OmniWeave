from pathlib import Path
import json

from core.planner import create_plan
from core.orchestrator import Orchestrator
from core.recovery import RecoveryManager
from storage.state_manager import StateManager
from tools.mcp_client import client


def build_report(goal, results):
    """Build a report from actual outputs returned by earlier tools."""
    sections = [
        "OMNIWEAVE EXECUTION REPORT",
        "=" * 30,
        f"User goal: {goal}",
        "",
        "Results from executed tools:",
    ]

    for index, item in enumerate(results, start=1):
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


def main():
    project_dir = Path(__file__).resolve().parent
    csv_path = project_dir / "data" / "sales.csv"
    report_path = project_dir / "output" / "omniweave_report.txt"

    if not csv_path.exists():
        print("ERROR: data/sales.csv was not found.")
        return

    goal = "Analyze this CSV dataset and create a report."
>>>>>>> Stashed changes

    print("\n=== OMNIWEAVE RESULT ===")
    print("Status:", result["status"])
    print("Goal:", result["goal"])
    print("Message:", result["message"])

<<<<<<< Updated upstream
    if result["plan"]:
        print("\n=== PLAN ===")
        for step in result["plan"].get("steps", []):
            print(
                step["step_id"],
                "->",
                step["tool_name"],
                ":",
                step["purpose"],
            )

    if result["execution"] is not None:
        print("\n=== EXECUTION ===")
        print(result["execution"])
=======
    # 1. Generate a plan using the team's planner.
    plan = create_plan(
        goal=goal,
        attachments=[{
            "name": "sales.csv",
            "path": str(csv_path),
        }],
    )

    print("\n========== GENERATED PLAN ==========")
    print(json.dumps(plan, indent=2, default=str))

    if plan.get("status") != "ready":
        print("\nPlanning did not complete successfully.")
        return

    # 2. Adapt the planner's step format for our orchestrator.
    integrated_plan = dict(plan)
    integrated_plan["steps"] = []

    for original_step in plan.get("steps", []):
        step = dict(original_step)
        step["id"] = step.get("step_id")
        step["description"] = step.get(
            "purpose",
            step.get("step_id", "Execute tool"),
        )
        integrated_plan["steps"].append(step)

    # 3. Connect the orchestrator to the team's registered tools.
    executed_results = []

    def invoke_tool(tool_name, arguments):
        arguments = dict(arguments or {})

        # Replace the planner's placeholder with real tool outputs.
        if tool_name == "create_report":
            arguments["content"] = build_report(
                goal,
                executed_results,
            )
            arguments.setdefault(
                "output_path",
                "output/omniweave_report.txt",
            )

        result = client.call_tool(tool_name, arguments)

        executed_results.append({
            "tool_name": tool_name,
            "result": result,
        })

        return result

    def show_event(**event):
        step_id = event.get("step_id")
        status = event.get("status", "unknown")
        message = event.get("message", "")
        prefix = f"[{step_id}] " if step_id else ""
        print(f"{status.upper()}: {prefix}{message}")

    state_manager = StateManager()
    recovery_manager = RecoveryManager(max_retries=2)
    orchestrator = Orchestrator(
        state_manager=state_manager,
        recovery_manager=recovery_manager,
    )

    print("\n========== EXECUTING WITH ORCHESTRATOR ==========")

    result = orchestrator.execute_plan(
        integrated_plan,
        invoke_tool,
        event_callback=show_event,
    )

    print("\n========== EXECUTION RESULT ==========")
    print(json.dumps(result, indent=2, default=str))

    # 4. Verify the report independently after execution.
    print("\n========== FINAL VERIFICATION ==========")

    report_exists = report_path.is_file()
    report_content = (
        report_path.read_text(encoding="utf-8")
        if report_exists
        else ""
    )
    report_nonempty = bool(report_content.strip())
    report_contains_goal = goal in report_content

    print("Task status:", result.get("status"))
    print("Report file exists:", report_exists)
    print("Report is non-empty:", report_nonempty)
    print("Report contains the user goal:", report_contains_goal)
    print("Report location:", report_path)

    verified = (
        result.get("status") == "completed"
        and report_exists
        and report_nonempty
        and report_contains_goal
    )

    if report_nonempty:
        print("\nREPORT CONTENT:\n")
        print(report_content)

    if verified:
        print("\nSUCCESS: Integrated workflow completed and report verified.")
    else:
        print("\nWORKFLOW NOT FULLY SUCCESSFUL.")
        print("Review the execution errors and verification results.")


if __name__ == "__main__":
    main()
