
import unittest

from core.plan_validator import validate_plan


class TestPlanValidator(unittest.TestCase):

    def setUp(self):
        self.tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {
                    "file_path": "string",
                },
            },
            {
                "name": "create_report",
                "description": "Create a report",
                "input_schema": {
                    "content": "string",
                    "output_path": "string",
                },
            },
        ]

    def valid_plan(self):
        return {
            "status": "ready",
            "steps": [
                {
                    "step_id": "step_1",
                    "tool_name": "read_file",
                    "arguments": {"file_path": "data/sales.csv"},
                    "dependencies": [],
                },
                {
                    "step_id": "step_2",
                    "tool_name": "create_report",
                    "arguments": {
                        "content": "Example report",
                        "output_path": "output/report.txt",
                    },
                    "dependencies": ["step_1"],
                },
            ],
        }

    def test_valid_plan(self):
        self.assertEqual(
            validate_plan(self.valid_plan(), self.tools),
            [],
        )

    def test_missing_argument(self):
        plan = self.valid_plan()
        plan["steps"][0]["arguments"] = {}

        errors = validate_plan(plan, self.tools)

        self.assertTrue(
            any("file_path" in error for error in errors)
        )

    def test_unknown_tool(self):
        plan = self.valid_plan()
        plan["steps"][0]["tool_name"] = "unknown_tool"

        errors = validate_plan(plan, self.tools)

        self.assertTrue(
            any("unavailable tool" in error.lower() for error in errors)
        )

    def test_duplicate_step_ids(self):
        plan = self.valid_plan()
        plan["steps"][1]["step_id"] = "step_1"

        errors = validate_plan(plan, self.tools)

        self.assertTrue(
            any("unique" in error.lower() for error in errors)
        )

    def test_invalid_dependency(self):
        plan = self.valid_plan()
        plan["steps"][1]["dependencies"] = ["step_99"]

        errors = validate_plan(plan, self.tools)

        self.assertTrue(
            any("preceding step" in error.lower() for error in errors)
        )

    def test_unready_plan(self):
        plan = self.valid_plan()
        plan["status"] = "unsupported"

        errors = validate_plan(plan, self.tools)

        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
