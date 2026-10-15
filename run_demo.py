
from pathlib import Path
from core.agent import run_agent


def main():
    csv_path = Path("data/sales.csv")

    result = run_agent(
        goal="Analyze the sales CSV file and create a report.",
        attachments=[
            {
                "name": "sales.csv",
                "path": str(csv_path),
            }
        ],
    )

    print("\n=== OMNIWEAVE RESULT ===")
    print("Status:", result["status"])
    print("Goal:", result["goal"])
    print("Message:", result["message"])

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


if __name__ == "__main__":
    main()
