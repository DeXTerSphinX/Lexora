"""
Lexora Question Cleaner

Removes layout artifacts from parsed exam questions while preserving
semantic numbers such as years, quantities, and ranges.
"""

import re
from typing import List


def _remove_mark_equations(text: str) -> str:
    """
    Remove patterns like '5 2=10' or '2 4=8'
    """
    return re.sub(r"\b\d+\s+\d+=\d+\b", "", text)


def _remove_paragraph_numbers(text: str) -> str:
    """
    Remove paragraph numbering inside passages, preserving line structure.

    Examples:
    '1 Very often...' -> 'Very often...'
    '6 1 Our history...' -> 'Our history...'
    """

    lines = []
    for line in text.split('\n'):
        # Strip leading paragraph number(s) before a capital letter
        line = re.sub(r"^\d+(?:\s+\d+)*\s+(?=[A-Z])", "", line)
        lines.append(line)
    return '\n'.join(lines)


def _remove_subquestion_marks(text: str) -> str:
    """
    Remove marks that appear after subquestions.

    Example:
    '(iii) 2' -> '(iii)'
    '(ii) 4' -> '(ii)'
    """

    return re.sub(r"\)[ \t]+\d+\b", ")", text)


def _remove_trailing_marks(text: str) -> str:
    """
    Remove numbers that appear after punctuation on the same line.

    Example:
    'about 50 words. 3' -> 'about 50 words.'
    """

    return re.sub(r"([\.\?\!])[ \t]+\d+\b", r"\1", text)


def _remove_question_mark_values(text: str) -> str:
    """
    Remove question marks column numbers on the same line.

    Example:
    'below : 6 Our history...' -> 'below : Our history...'
    """

    return re.sub(r":[ \t]+\d+[ \t]+(?=[A-Z])", ": ", text)


def _normalize_ranges(text: str) -> str:
    """
    Fix numeric ranges like '120 150 words'
    """

    return re.sub(r"\b(\d+)\s+(\d+)\s+words\b", r"\1–\2 words", text)


def _normalize_spacing(text: str) -> str:
    """
    Normalize whitespace and punctuation spacing.
    Collapses horizontal whitespace only — newlines are preserved
    so multi-line question blocks keep their line structure.
    """

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]+\.", ".", text)
    text = re.sub(r"[ \t]+,", ",", text)

    return text.strip()


def clean_question_text(question: str) -> str:
    """
    Clean a single parsed question block.
    """

    text = question

    text = _remove_mark_equations(text)
    text = _remove_paragraph_numbers(text)
    text = _remove_subquestion_marks(text)
    text = _remove_trailing_marks(text)
    text = _remove_question_mark_values(text)
    text = _normalize_ranges(text)
    text = _normalize_spacing(text)

    return text


def clean_questions(questions: List[str]) -> List[str]:
    """
    Clean all parsed questions.
    """

    return [clean_question_text(q) for q in questions]


def _clean_field(text: str, keep_paragraph_numbers: bool = False) -> str:
    """
    Clean an individual text field extracted by the analyzer.
    """

    if not text:
        return text

    text = _remove_mark_equations(text)

    if not keep_paragraph_numbers:
        text = _remove_paragraph_numbers(text)

    text = _remove_subquestion_marks(text)
    text = _remove_trailing_marks(text)
    text = _remove_question_mark_values(text)
    text = _normalize_ranges(text)
    text = _normalize_spacing(text)

    return text


def clean_analyzed_question(analyzed):
    """
    Clean the text fields of an already-analyzed question dict in place.
    Passages keep paragraph numbers so the frontend can split on them.
    """

    if analyzed.get("header"):
        analyzed["header"] = _clean_field(analyzed["header"])

    if analyzed.get("passage"):
        analyzed["passage"] = _clean_field(analyzed["passage"], keep_paragraph_numbers=True)

    if analyzed.get("instruction"):
        analyzed["instruction"] = _clean_field(analyzed["instruction"])

    for sq in analyzed.get("subquestions", []):
        if sq.get("text"):
            sq["text"] = _clean_field(sq["text"])