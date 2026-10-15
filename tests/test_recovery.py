
import tempfile
import unittest
from pathlib import Path

from core.orchestrator import Orchestrator
from core.recovery import RecoveryManager
from storage.state_manager import StateManager


class TestRecovery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.db"

        self.state_manager = StateManager(db_path)
        self.orchestrator = Orchestrator(
            state_manager=self.state_manager,
            recovery_manager=RecoveryManager(max_retries=2),
        )

        self.plan = {
            "goal": "Test retry and resume",
            "steps": [
                {
                    "id": "step_1",
                    "description": "Run test tool",
                    "tool_name": "fake_tool",
                    "arguments": {},
                    "dependencies": [],
                    "expected_output": "Success",
                    "acceptance_criteria": ["Tool succeeds"],
                }
            ],
            "acceptance_criteria": ["Task completes"],
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_retries_failure_and_completes(self):
        calls = {"count": 0}

        def fake_tool(tool_name, arguments):
            calls["count"] += 1

            if calls["count"] == 1:
                return {
                    "success": False,
                    "error": "Temporary tool failure",
                    "retryable": True,
                }

            return {
                "success": True,
                "output": {"message": "Operation completed"},
            }

        result = self.orchestrator.execute_plan(self.plan, fake_tool)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(calls["count"], 2)
        self.assertEqual(
            self.state_manager.get_completed_step_ids(result["task_id"]),
            {"step_1"},
        )

    def test_does_not_repeat_completed_step_on_resume(self):
        calls = {"count": 0}

        def fake_tool(tool_name, arguments):
            calls["count"] += 1
            return {
                "success": True,
                "output": {"message": "Done"},
            }

        first = self.orchestrator.execute_plan(self.plan, fake_tool)

        self.assertEqual(first["status"], "completed")
        self.assertEqual(calls["count"], 1)

        def should_not_run(tool_name, arguments):
            raise AssertionError("Completed step ran again")

        second = self.orchestrator.execute_plan(
            self.plan,
            should_not_run,
            task_id=first["task_id"],
        )

        self.assertEqual(second["status"], "completed")
        self.assertEqual(calls["count"], 1)

    def test_permanent_failure_is_not_retried(self):
        calls = {"count": 0}

        def fake_tool(tool_name, arguments):
            calls["count"] += 1
            return {
                "success": False,
                "error": "Invalid arguments",
                "retryable": False,
            }

        result = self.orchestrator.execute_plan(self.plan, fake_tool)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(calls["count"], 1)

    def test_max_retries_means_retries_after_initial_attempt(self):
        calls = {"count": 0}

        def fake_tool(tool_name, arguments):
            calls["count"] += 1
            return {
                "success": False,
                "error": "Temporary failure",
                "retryable": True,
            }

        result = self.orchestrator.execute_plan(self.plan, fake_tool)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(calls["count"], 3)

    def test_dependent_step_does_not_run_after_failure(self):
        plan = {
            "goal": "Test dependencies",
            "steps": [
                {
                    "id": "step_1",
                    "description": "Fail",
                    "tool_name": "first",
                    "arguments": {},
                    "dependencies": [],
                    "expected_output": "Success",
                    "acceptance_criteria": [],
                },
                {
                    "id": "step_2",
                    "description": "Depends on first",
                    "tool_name": "second",
                    "arguments": {},
                    "dependencies": ["step_1"],
                    "expected_output": "Success",
                    "acceptance_criteria": [],
                },
            ],
            "acceptance_criteria": [],
        }

        invoked = []

        def fake_tool(tool_name, arguments):
            invoked.append(tool_name)
            return {
                "success": False,
                "error": "Permanent failure",
                "retryable": False,
            }

        result = self.orchestrator.execute_plan(plan, fake_tool)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(invoked, ["first"])
        self.assertNotIn(
            "step_2",
            self.state_manager.get_completed_step_ids(result["task_id"]),
        )

    def test_dependency_executes_before_dependent_step(self):
        execution_order = []

        def fake_tool(tool_name, arguments):
            execution_order.append(tool_name)
            return {
                "success": True,
                "output": f"{tool_name} completed",
            }

        plan = {
            "goal": "Test dependency ordering",
            "steps": [
                {
                    "id": "step_1",
                    "description": "Analyze data",
                    "tool_name": "analyze_data",
                    "arguments": {},
                    "dependencies": [],
                    "expected_output": "Analysis results",
                    "acceptance_criteria": [],
                },
                {
                    "id": "step_2",
                    "description": "Generate report",
                    "tool_name": "generate_report",
                    "arguments": {},
                    "dependencies": ["step_1"],
                    "expected_output": "Report",
                    "acceptance_criteria": [],
                },
            ],
            "acceptance_criteria": [],
        }

        result = self.orchestrator.execute_plan(
            plan,
            invoke_tool=fake_tool,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            execution_order,
            ["analyze_data", "generate_report"],
        )

    def test_task_state_persists_after_reopening_database(self):
        task_id = self.state_manager.create_task(self.plan)

        self.state_manager.update_step(
            task_id=task_id,
            step_id="step_1",
            status="completed",
            attempts=1,
            result={"message": "Analysis completed"},
        )

        self.state_manager.set_task_status(task_id, "completed")

        # Open a new StateManager using the same database file.
        db_path = Path(self.temp_dir.name) / "test.db"
        reopened_manager = StateManager(db_path)

        saved_task = reopened_manager.get_task(task_id)
        completed_steps = reopened_manager.get_completed_step_ids(task_id)

        self.assertIsNotNone(saved_task)
        self.assertEqual(saved_task["status"], "completed")
        self.assertEqual(completed_steps, {"step_1"})

        saved_steps = reopened_manager.get_steps(task_id)
        step = next(s for s in saved_steps if s["step_id"] == "step_1")

        self.assertEqual(step["status"], "completed")
        self.assertEqual(step["attempts"], 1)
        self.assertEqual(step["result"], {"message": "Analysis completed"})


    def test_resume_after_failure_skips_completed_step(self):
        plan = {
            "goal": "Test recovery after partial completion",
            "steps": [
                {
                    "id": "step_1",
                    "description": "Analyze data",
                    "tool_name": "analyze_data",
                    "arguments": {},
                    "dependencies": [],
                    "expected_output": "Analysis results",
                    "acceptance_criteria": [],
                },
                {
                    "id": "step_2",
                    "description": "Generate report",
                    "tool_name": "generate_report",
                    "arguments": {},
                    "dependencies": ["step_1"],
                    "expected_output": "Report",
                    "acceptance_criteria": [],
                },
            ],
            "acceptance_criteria": [],
        }

        calls = {"analyze_data": 0, "generate_report": 0}

        def first_attempt(tool_name, arguments):
            calls[tool_name] += 1

            if tool_name == "generate_report":
                return {
                    "success": False,
                    "error": "Temporary report failure",
                    "retryable": False,
                }

            return {
                "success": True,
                "output": {"message": "Analysis completed"},
            }

        first = self.orchestrator.execute_plan(plan, first_attempt)

        self.assertEqual(first["status"], "failed")
        self.assertEqual(calls["analyze_data"], 1)

        def second_attempt(tool_name, arguments):
            calls[tool_name] += 1
            return {
                "success": True,
                "output": {"message": "Report generated"},
            }

        resumed = self.orchestrator.execute_plan(
            plan,
            second_attempt,
            task_id=first["task_id"],
        )

        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(calls["analyze_data"], 1)
        self.assertEqual(calls["generate_report"], 2)

    def test_circular_dependencies_are_rejected(self):
        plan = {
            "goal": "Test circular dependency rejection",
            "steps": [
                {
                    "id": "step_1",
                    "description": "First step",
                    "tool_name": "first",
                    "arguments": {},
                    "dependencies": ["step_2"],
                    "expected_output": "First result",
                    "acceptance_criteria": [],
                },
                {
                    "id": "step_2",
                    "description": "Second step",
                    "tool_name": "second",
                    "arguments": {},
                    "dependencies": ["step_1"],
                    "expected_output": "Second result",
                    "acceptance_criteria": [],
                },
            ],
            "acceptance_criteria": [],
        }

        def should_not_run(tool_name, arguments):
            self.fail("A tool must not run for a circular plan")

        with self.assertRaises(ValueError):
            self.orchestrator.execute_plan(plan, should_not_run)


if __name__ == "__main__":
    unittest.main()
