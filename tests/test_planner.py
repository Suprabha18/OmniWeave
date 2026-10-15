
import unittest

from core.planner import create_plan, validate_plan


class TestPlanner(unittest.TestCase):

    def test_creates_csv_analysis_plan(self):
        plan = create_plan(
            goal="Analyze this CSV dataset.",
            attachments=[
                {
                    "name": "sales.csv",
                    "path": "data/sales.csv",
                }
            ],
        )

        self.assertEqual(plan["status"], "ready")

        tool_names = [
            step["tool_name"]
            for step in plan["steps"]
        ]

        self.assertIn("read_file", tool_names)
        self.assertIn("analyze_csv", tool_names)

    def test_creates_report_and_verification_steps(self):
        plan = create_plan(
            goal="Analyze this CSV and create a report.",
            attachments=[
                {
                    "name": "sales.csv",
                    "path": "data/sales.csv",
                }
            ],
        )

        tool_names = [
            step["tool_name"]
            for step in plan["steps"]
        ]

        self.assertIn("create_report", tool_names)
        self.assertIn("read_saved_report", tool_names)

    def test_missing_goal_needs_clarification(self):
        plan = create_plan(goal="")

        self.assertEqual(
            plan["status"],
            "needs_clarification",
        )
        self.assertTrue(plan["clarification_questions"])

    def test_missing_analysis_tool_is_reported(self):
        plan = create_plan(
            goal="Analyze this CSV dataset.",
            attachments=[
                {
                    "name": "sales.csv",
                    "path": "data/sales.csv",
                }
            ],
            available_tools=[
                {
                    "name": "read_file",
                    "description": "Read a supported input file.",
                    "input_schema": {"file_path": "string"},
                }
            ],
        )

        self.assertEqual(plan["status"], "unsupported")
        self.assertTrue(plan["errors"])

    def test_unknown_dependency_is_detected(self):
        plan = {
            "steps": [
                {
                    "step_id": "step_1",
                    "tool_name": "read_file",
                    "dependencies": ["step_unknown"],
                }
            ]
        }

        errors = validate_plan(
            plan,
            available_tool_names={"read_file"},
        )

        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
