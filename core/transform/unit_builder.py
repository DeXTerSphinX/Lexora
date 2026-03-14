"""
Lexora Transformation Unit Builder

Converts analyzed questions into transformation units
while preserving exam structure.
"""

import re


QUESTION_NUMBER_PATTERN = re.compile(r'^(\d+)\.\s*(.*)')


def _split_question_number(header):

    match = QUESTION_NUMBER_PATTERN.match(header)

    if match:
        number = match.group(1)
        text = match.group(2)
        return number, text

    return None, header


def build_units(question_index, analyzed_question):

    units = []

    qid = f"Q{question_index}"

    header = analyzed_question.get("header") or ""
    header_marks = analyzed_question.get("header_marks")

    q_number, header_text = _split_question_number(header)

    units.append({
        "id": f"{qid}.header",
        "type": "header",
        "question_number": q_number,
        "text": header_text,
        "marks": header_marks
    })

    passage = analyzed_question.get("passage")

    if passage:
        units.append({
            "id": f"{qid}.passage",
            "type": "passage",
            "text": passage,
            "marks": None
        })

    instruction = analyzed_question.get("instruction")
    instruction_marks = analyzed_question.get("instruction_marks")

    if instruction:
        units.append({
            "id": f"{qid}.instruction",
            "type": "instruction",
            "text": instruction,
            "marks": instruction_marks
        })

    subquestions = analyzed_question.get("subquestions", [])

    for sq in subquestions:

        label = sq.get("label")
        text = sq.get("text")
        marks = sq.get("marks")
        incomplete = sq.get("incomplete", False)

        unit_id = f"{qid}{label}"

        units.append({
            "id": unit_id,
            "type": "subquestion",
            "label": label,
            "text": text if text else "",
            "marks": marks,
            "incomplete": incomplete
        })

    return units


def build_units_from_exam(analyzed_questions):

    all_units = []

    for index, question in enumerate(analyzed_questions, start=1):

        units = build_units(index, question)

        all_units.extend(units)

    return all_units