
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.demo_tools import (
    read_file,
    analyze_csv,
    create_report,
    read_saved_report,
    simulate_failure,
)
from tools.registry import list_tools, execute_tool


class TestDemoTools(unittest.TestCase):

    def setUp(self):
        # Create a temporary folder for test files.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name)
        self.csv_path = self.root / "sales.csv"

        # Create a sample CSV dataset.
        with self.csv_path.open(
            "w", encoding="utf-8", newline=""
        ) as file:
            writer = csv.DictWriter(
                file, fieldnames=["product", "sales"]
            )
            writer.writeheader()
            writer.writerow({"product": "A", "sales": "100"})
            writer.writerow({"product": "B", "sales": "50"})

    def test_read_csv(self):
        result = read_file(str(self.csv_path))

        self.assertTrue(result["success"])
        self.assertEqual(result["row_count"], 2)
        self.assertIn("product", result["columns"])

    def test_analyze_csv(self):
        result = analyze_csv(str(self.csv_path))

        self.assertTrue(result["success"])
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(
            result["numeric_summary"]["sales"]["total"],
            150.0,
        )

    def test_missing_file(self):
        missing_path = self.root / "missing.csv"

        with self.assertRaises(FileNotFoundError):
            read_file(str(missing_path))

    def test_create_and_read_report(self):
        output_dir = self.root / "output"
        report_path = output_dir / "report.txt"

        # Use a temporary output directory for this test.
        with patch("tools.demo_tools.OUTPUT_DIR", output_dir):
            saved = create_report(
                "OmniWeave test report",
                str(report_path),
            )

            verified = read_saved_report(str(report_path))

        self.assertTrue(saved["success"])
        self.assertTrue(verified["exists"])
        self.assertIn(
            "OmniWeave test report",
            verified["content"],
        )

    def test_registry_lists_and_executes_tools(self):
        tool_names = {
            tool["name"] for tool in list_tools()
        }

        self.assertIn("read_file", tool_names)
        self.assertIn("analyze_csv", tool_names)
        self.assertIn("create_report", tool_names)

        result = execute_tool(
            "read_file",
            {"file_path": str(self.csv_path)},
        )

        self.assertTrue(result["success"])

    def test_simulated_failure(self):
        with self.assertRaises(RuntimeError):
            simulate_failure()


if __name__ == "__main__":
    unittest.main()
