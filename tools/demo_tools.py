
import csv
import json
from pathlib import Path
from statistics import mean


OUTPUT_DIR = Path("output")

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".xml", ".html"
}


def read_file(file_path):
    """Read a supported text file or CSV file."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise ValueError("The supplied path is not a file.")

    extension = path.suffix.lower()

    if extension == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            rows = list(reader)

        return {
            "success": True,
            "file_path": str(path),
            "columns": reader.fieldnames or [],
            "row_count": len(rows),
            "content": rows,
        }

    if extension in SUPPORTED_TEXT_EXTENSIONS:
        content = path.read_text(encoding="utf-8")

        if extension == ".json":
            try:
                content = json.loads(content)
            except json.JSONDecodeError as error:
                raise ValueError("The file contains invalid JSON.") from error

        return {
            "success": True,
            "file_path": str(path),
            "content": content,
        }

    raise ValueError(
        f"Unsupported file type: {extension}. "
        "This demo supports CSV and common text-based files."
    )


def analyze_csv(file_path):
    """Summarize a CSV and calculate basic numeric statistics."""

    data = read_file(file_path)

    if Path(file_path).suffix.lower() != ".csv":
        raise ValueError("analyze_csv requires a CSV file.")

    rows = data["content"]
    columns = data["columns"]

    numeric_summary = {}

    for column in columns:
        values = []

        for row in rows:
            raw_value = row.get(column)

            if raw_value is None:
                continue

            try:
                values.append(float(raw_value))
            except (TypeError, ValueError):
                continue

        if values:
            numeric_summary[column] = {
                "count": len(values),
                "total": round(sum(values), 2),
                "average": round(mean(values), 2),
                "minimum": min(values),
                "maximum": max(values),
            }

    return {
        "success": True,
        "file_path": str(file_path),
        "row_count": len(rows),
        "columns": columns,
        "numeric_summary": numeric_summary,
        "sample_rows": rows[:5],
    }


def create_report(content, output_path="output/omniweave_report.txt"):
    """Save text or structured data as a report."""

    path = Path(output_path)

    # Keep generated reports inside the output directory.
    output_root = OUTPUT_DIR.resolve()
    resolved_path = path.resolve()

    if not resolved_path.is_relative_to(output_root):
        raise ValueError("Reports must be saved inside the output folder.")

    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(content, str):
        report_text = content
    else:
        report_text = json.dumps(content, indent=2, ensure_ascii=False)

    path.write_text(report_text, encoding="utf-8")

    return {
        "success": True,
        "output_path": str(path),
        "characters_written": len(report_text),
    }


def read_saved_report(file_path="output/omniweave_report.txt"):
    """Read a saved report to check that it was created correctly."""

    path = Path(file_path).resolve()
    output_root = OUTPUT_DIR.resolve()

    if not path.is_relative_to(output_root):
        raise ValueError("Reports must be read from the output folder.")

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Saved report not found: {file_path}")

    content = path.read_text(encoding="utf-8")

    return {
        "success": True,
        "file_path": str(path),
        "exists": True,
        "characters_read": len(content),
        "content": content,
    }


def simulate_failure():
    """Test how OmniWeave handles a tool that fails."""

    raise RuntimeError("Simulated tool failure for recovery testing.")
