
from pathlib import Path
import json

from core.planner import create_plan
from core.executor import execute_plan


def main():
    project_dir = Path(__file__).resolve().parent
    csv_path = project_dir / "data" / "sales.csv"

    if not csv_path.exists():
        print("ERROR: data/sales.csv was not found.")
        return

    goal = (
        "Analyze this CSV dataset and create a report."
    )

    print("\n========== OMNIWEAVE REAL-TIME TEST ==========")
    print("\nUSER GOAL:")
    print(goal)

    # 1. Create a plan using the actual planner.
    plan = create_plan(
        goal=goal,
        attachments=[{
            "name": "sales.csv",
            "path": str(csv_path),
        }],
    )

    print("\n========== GENERATED PLAN ==========")
    print(json.dumps(plan, indent=2, default=str))

    if plan["status"] != "ready":
        print("\nPlanning did not complete successfully.")
        return

    # 2. Execute the plan using real registered Python tools.
    print("\n========== EXECUTING PLAN ==========")

    result = execute_plan(plan)

    print("\n========== EXECUTION RESULT ==========")
    print(json.dumps(result, indent=2, default=str))

    # 3. Check whether the report exists on disk.
    report_path = project_dir / "output" / "omniweave_report.txt"

    print("\n========== FINAL VERIFICATION ==========")

    if report_path.exists():
        report_content = report_path.read_text(encoding="utf-8")

        print("Report file exists:", True)
        print("Report is non-empty:", bool(report_content.strip()))
        print("Report location:", report_path)
        print("\nREPORT CONTENT:\n")
        print(report_content)
    else:
        print("Report file exists:", False)

    if result["status"] == "completed" and report_path.exists():
        print("\nSUCCESS: End-to-end workflow completed.")
    else:
        print("\nWORKFLOW NOT FULLY SUCCESSFUL.")
        print("Check the execution errors printed above.")


if __name__ == "__main__":
    main()
