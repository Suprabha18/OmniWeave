
import re
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".txt", ".csv", ".pdf", ".json", ".md",
    ".docx", ".xlsx", ".xml", ".html"
}

FILE_REFERENCE_PATTERN = re.compile(
    r"\b(attached|uploaded|provided)\s+"
    r"(?:file|document|report|spreadsheet|dataset|pdf|csv|text)\b"
    r"|\b(?:this|the)\s+(?:file|document|attachment|spreadsheet)\b",
    re.IGNORECASE,
)


def interpret_goal(
    goal,
    input_text=None,
    attachments=None,
    constraints=None,
):
    """
    Interpret a user's goal independently of input format.

    Parameters:
        goal: Natural-language instruction from the user.
        input_text: Optional source text, including lengthy text.
        attachments: Optional list of file paths or file metadata.
        constraints: Optional user-defined constraints.

    Returns:
        A structured dictionary ready for the planning engine.
    """

    if not isinstance(goal, str) or not goal.strip():
        return {
            "status": "needs_clarification",
            "goal": "",
            "objective": "",
            "input_text": input_text or "",
            "input_files": [],
            "attachments": [],
            "constraints": constraints or [],
            "desired_outputs": [],
            "clarification_questions": [
                "What would you like OmniWeave to accomplish?"
            ],
        }

    goal = goal.strip()
    input_text = input_text if isinstance(input_text, str) else ""

    # Normalize attachment descriptions into a consistent structure.
    normalized_attachments = []

    for attachment in attachments or []:
        if isinstance(attachment, (str, Path)):
            path = str(attachment)
            normalized_attachments.append({
                "name": Path(path).name,
                "path": path,
                "extension": Path(path).suffix.lower(),
            })

        elif isinstance(attachment, dict):
            path = attachment.get("path")
            name = attachment.get("name") or (
                Path(path).name if path else "unnamed"
            )

            extension = attachment.get(
                "extension",
                Path(name).suffix,
            ).lower()

            normalized_attachments.append({
                "name": name,
                "path": path,
                "extension": extension,
                "content_type": attachment.get("content_type"),
            })

    input_files = [
        item["path"]
        for item in normalized_attachments
        if item.get("path")
    ]

    # Recognize filenames explicitly written in the user's goal.
    filename_pattern = re.compile(
        r"""["']([^"']+\.[a-zA-Z0-9]+)["']"""
    )

    for filename in filename_pattern.findall(goal):
        extension = Path(filename).suffix.lower()

        if extension in SUPPORTED_EXTENSIONS:
            if filename not in input_files:
                input_files.append(filename)

    # Keep constraints supplied by the caller and add simple
    # constraints explicitly expressed in the goal.
    extracted_constraints = list(constraints or [])

    limit_match = re.search(
        r"\b(?:top|first|at most|maximum of)\s+(\d+)\b",
        goal,
        re.IGNORECASE,
    )

    if limit_match:
        extracted_constraints.append({
            "type": "limit",
            "value": int(limit_match.group(1)),
        })

    # Preserve the complete goal as the objective description.
    # Do not reduce the user's request to a narrow fixed category.
    objective = goal

    # Infer output preferences without restricting the domain.
    normalized_goal = goal.lower()
    desired_outputs = []

    output_patterns = [
        (
            "summary",
            r"\b(summarize|summarise|summary|key points)\b",
        ),
        (
            "report",
            r"\b(report|document|write-up)\b",
        ),
        (
            "table",
            r"\b(table|tabular)\b",
        ),
        (
            "chart",
            r"\b(chart|graph|visualization|visualisation)\b",
        ),
        (
            "comparison",
            r"\b(compare|comparison|differences)\b",
        ),
        (
            "analysis_results",
            r"\b(analyze|analyse|analysis|calculate|statistics)\b",
        ),
        (
            "code",
            r"\b(write code|generate code|implement|program)\b",
        ),
    ]

    for output_type, pattern in output_patterns:
        if re.search(pattern, normalized_goal):
            desired_outputs.append({
                "type": output_type,
            })

    questions = []

    # Ask for a file only when the goal refers to one but none
    # was provided. Text-only tasks remain valid.
    refers_to_file = bool(
        FILE_REFERENCE_PATTERN.search(goal)
    )

    if refers_to_file and not normalized_attachments and not input_files:
        if not input_text.strip():
            questions.append(
                "Please upload the referenced file or paste its contents."
            )

    if (
        not input_text.strip()
        and not normalized_attachments
        and not input_files
        and re.search(
            r"\b(this text|the following text|below text|"
            r"attached text|provided text)\b",
            normalized_goal,
        )
    ):
        questions.append(
            "Please provide the text you want OmniWeave to process."
        )

    return {
        "status": (
            "needs_clarification" if questions else "ready"
        ),
        "goal": goal,
        "objective": objective,
        "input_text": input_text,
        "input_files": input_files,
        "attachments": normalized_attachments,
        "constraints": extracted_constraints,
        "desired_outputs": desired_outputs,
        "clarification_questions": questions,
    }
