
import unittest

from core.executor import execute_plan


class FakeToolClient:
    """A predictable tool client for executor tests."""

    def __init__(self, fail_on=None):
        self.fail_on = fail_on
        self.calls = []

    def discover_tools(self):
        return [
            {"name": "read_file"},
            {"name": "analyze_csv"},
            {"name": "create_report"},
            {"name": "read_saved_report"},
            {"name": "simulate_failure"},
        ]

    def call_tool(self, tool_name, arguments=None):
        arguments = arguments or {}
        self.calls.append((tool_name, arguments))

        if tool_name == self.fail_on:
            raise RuntimeError("Test failure")

        if tool_name == "read_file":
            return {
                "success": True,
                "content": [{"product": "A", "sales": 100}],
            }

        if tool_name == "analyze_csv":
            return {
                "success": True,
                "summary": {"sales_total": 100},
            }

        if tool_name == "create_report":
            return {
                "success": True,
                "output_path": arguments["output_path"],
            }

        if tool_name == "read_saved_report":
            return {
                "success": True,
                "exists": True,
                "content": "Verified report content",
            }

        return {"success": True}


def sample_plan():
    return {
        "status": "ready",
        "goal": "Analyze sales and save a report.",
        "steps": [
            {
                "step_id": "step_1",
                "tool_name": "read_file",
                "arguments": {"file_path": "sales.csv"},
                "dependencies": [],
            },
            {
                "step_id": "step_2",
                "tool_name": "analyze_csv",
                "arguments": {"file_path": "sales.csv"},
                "dependencies": ["step_1"],
            },
            {
                "step_id": "step_3",
                "tool_name": "create_report",
                "arguments": {
                    "content": (
                        "Use the outputs of the preceding steps "
                        "to prepare the requested report."
                    ),
                    "output_path": "output/omniweave_report.txt",
                },
                "dependencies": ["step_1", "step_2"],
            },
            {
                "step_id": "step_4",
                "tool_name": "read_saved_report",
                "arguments": {
                    "file_path": "output/omniweave_report.txt"
                },
                "dependencies": ["step_3"],
            },
        ],
    }


class TestExecutor(unittest.TestCase):

    def test_executes_steps_in_order(self):
        fake = FakeToolClient()
        result = execute_plan(sample_plan(), tool_client=fake)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            result["completed_steps"],
            ["step_1", "step_2", "step_3", "step_4"],
        )

    def test_report_uses_actual_results(self):
        fake = FakeToolClient()
        execute_plan(sample_plan(), tool_client=fake)

        report_call = next(
            args for name, args in fake.calls
            if name == "create_report"
        )

        self.assertIn("sales_total", report_call["content"])
        self.assertNotIn(
            "Use the outputs of the preceding steps",
            report_call["content"],
        )

    def test_failure_stops_execution(self):
        fake = FakeToolClient(fail_on="analyze_csv")
        result = execute_plan(sample_plan(), tool_client=fake)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed_step"], "step_2")

        called_tools = [name for name, _ in fake.calls]
        self.assertEqual(called_tools, ["read_file", "analyze_csv"])
        self.assertTrue(result["errors"])

    def test_report_verification_is_recorded(self):
        fake = FakeToolClient()
        result = execute_plan(sample_plan(), tool_client=fake)

        self.assertTrue(result["report_verified"])

    def test_unready_plan_does_not_execute(self):
        fake = FakeToolClient()
        plan = {
            "status": "needs_clarification",
            "goal": "",
            "steps": [],
        }

        result = execute_plan(plan, tool_client=fake)

        self.assertEqual(result["status"], "not_started")
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
