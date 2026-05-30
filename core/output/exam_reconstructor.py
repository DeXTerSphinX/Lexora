"""
Exam Reconstructor

Rebuilds the transformed exam while preserving structure
and improving readability.
"""

import re
from core.ingestion.question_cleaner import _normalize_ranges, _normalize_spacing


def clean_line_breaks(text):
    """
    Merges broken line wraps caused by PDF extraction.
    """

    if not text:
        return text

    # Merge newlines that occur in the middle of sentences
    text = re.sub(r'(?<!\n)\n(?!\n)(?=[a-z])', ' ', text)

    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def _clean_text(text):
    """
    Apply lightweight cleaning to output text.
    """

    if not text:
        return text

    text = _normalize_ranges(text)
    text = _normalize_spacing(text)

    return text


def format_passage(text):
    """
    Splits numbered paragraphs and cleans line wrapping.
    Only splits on paragraph numbers at the start of a sentence
    (digit followed by space then uppercase letter).
    """

    text = clean_line_breaks(text)

    # Split on paragraph numbers: a digit at a word boundary followed
    # by a space and an uppercase letter (e.g., "1 Very", "2 In")
    parts = re.split(r'(?=\b(\d+)\s+(?=[A-Z]))', text)

    formatted = []

    for p in parts:
        p = p.strip()
        if p and not re.match(r'^\d+$', p):
            formatted.append(p)

    return "\n\n".join(formatted)


def reconstruct_exam(results):

    output = []

    for unit in results:

        text = unit["modified"]
        unit_type = unit["type"]
        unit_id = unit["id"]
        marks = unit.get("marks")
        question_number = unit.get("question_number")

        if text is None:
            text = ""

        text = text.strip()
        text = _clean_text(text)

        # HEADER
        if unit_type == "header":

            # Restore question number
            prefix = f"{question_number}. " if question_number else ""

            if marks:
                output.append(f"\n{prefix}{text} ({marks})\n")
            else:
                output.append(f"\n{prefix}{text}\n")

        # PASSAGE
        elif unit_type == "passage":

            if text:
                text = format_passage(text)
                output.append(f"\n{text}\n")

        # INSTRUCTION
        elif unit_type == "instruction":

            if marks:
                output.append(f"\n{text} ({marks})\n")
            else:
                output.append(f"\n{text}\n")

        # SUBQUESTION
        elif unit_type == "subquestion":

            match = re.search(r"\((.*?)\)", unit_id)

            if match:
                label = f"({match.group(1)})"
            else:
                label = ""

            # Flag incomplete subquestions (PDF data missing)
            if not text:
                output.append(f"\n{label} [Text unavailable - PDF extraction issue] ({marks})\n")
                continue

            if marks:
                output.append(f"\n{label} {text} ({marks})\n")
            else:
                output.append(f"\n{label} {text}\n")

        else:

            if text:
                output.append(f"{text}\n")

    return "".join(output)
