
import unittest

from core.plan_builder import build_file_workflow


class TestPlanBuilder(unittest.TestCase):

    def setUp(self):
        self.tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {"file_path": "string"},
            },
            {
                "name": "analyze_csv",
                "description": "Analyze CSV",
                "input_schema": {"file_path": "string"},
            },
            {
                "name": "create_report",
                "description": "Create a report",
                "input_schema": {
                    "content": "string",
                    "output_path": "string",
                },
            },
            {
                "name": "read_saved_report",
                "description": "Verify a saved report",
                "input_schema": {"file_path": "string"},
            },
        ]

    def test_builds_analysis_and_report_workflow(self):
        plan = build_file_workflow(
            "Analyze the CSV and create a report",
            ["data/sales.csv"],
            self.tools,
        )

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(
            [step["tool_name"] for step in plan["steps"]],
            [
                "read_file",
                "analyze_csv",
                "create_report",
                "read_saved_report",
            ],
        )

    def test_report_depends_on_analysis(self):
        plan = build_file_workflow(
            "Analyze the CSV and create a report",
            ["data/sales.csv"],
            self.tools,
        )

        report_step = next(
            step for step in plan["steps"]
            if step["tool_name"] == "create_report"
        )

        self.assertIn("step_2", report_step["dependencies"])

    def test_missing_reader_is_reported(self):
        tools = [
            tool for tool in self.tools
            if tool["name"] != "read_file"
        ]

        plan = build_file_workflow(
            "Analyze the CSV",
            ["data/sales.csv"],
            tools,
        )

        self.assertEqual(plan["status"], "unsupported")
        self.assertTrue(plan["errors"])

    def test_analysis_without_csv_is_not_ready(self):
        plan = build_file_workflow(
            "Analyze the dataset",
            [],
            self.tools,
        )

        self.assertNotEqual(plan["status"], "ready")

    def test_empty_goal_needs_clarification(self):
        plan = build_file_workflow("", [], self.tools)

        self.assertEqual(plan["status"], "needs_clarification")


if __name__ == "__main__":
    unittest.main()
