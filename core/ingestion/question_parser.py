"""
Lexora Question Parser

Stage 1 parser.

Splits exam text into main question blocks while preserving line structure.
"""

import re
from typing import List


MAIN_QUESTION_PATTERN = re.compile(r"^\d+[.),:]\s")


def _normalize_lines(text: str) -> List[str]:

    lines = text.split("\n")

    cleaned = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        cleaned.append(line)

    return cleaned


def _strip_preamble(lines: List[str]) -> List[str]:
    """
    Remove everything before the first main question.
    Prevents general instructions, exam headers, and metadata
    from being parsed as question content.
    """

    for i, line in enumerate(lines):
        if MAIN_QUESTION_PATTERN.match(line):
            return lines[i:]

    return lines


def parse_questions(text: str) -> List[str]:

    lines = _normalize_lines(text)

    lines = _strip_preamble(lines)

    questions = []
    current_block = []

    for line in lines:

        if MAIN_QUESTION_PATTERN.match(line):

            if current_block:
                questions.append("\n".join(current_block))

            current_block = [line]

        else:

            if current_block:
                current_block.append(line)

    if current_block:
        questions.append("\n".join(current_block))

    return questions