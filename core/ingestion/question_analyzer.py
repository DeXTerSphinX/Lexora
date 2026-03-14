"""
Lexora Question Analyzer

Analyzes a question block and extracts:

- header text
- header marks
- passage
- instruction
- instruction marks
- subquestions
- marks for each subquestion
"""

import re


SUBQUESTION_PATTERN = re.compile(r'^\(([a-z]{1,4}|\d{1,2})\)', re.IGNORECASE)

SUBQUESTION_MARKS_PATTERN = re.compile(r'\b(\d+)\s*$')

INSTRUCTION_MARKS_PATTERN = re.compile(r'\d+\s*\d+=\d+$')

HEADER_MARKS_PATTERN = re.compile(r'\s(\d+(?:\s*\d+=\d+)?)$')

# A line is an instruction if it starts with one of these imperative/directive phrases.
# Keep only verbs that are unambiguously task-openers and do NOT appear in passage prose.
INSTRUCTION_STARTER = re.compile(
    r'^(answer|attempt|draft|write|describe|explain|discuss|analyse|analyze|'
    r'compare|evaluate|identify|calculate|compose|examine|justify|assess|'
    r'based on|in about|with reference)',
    re.IGNORECASE
)

# Matches an instruction verb appearing after a sentence-ending period inside
# passage text (e.g. "...celebrate her success. Draft a formal invitation...")
EMBEDDED_INSTRUCTION = re.compile(
    r'([.!?])\s+'
    r'((?:Answer|Attempt|Draft|Write|Describe|Explain|Discuss|Analyse|Analyze|'
    r'Compare|Evaluate|Identify|Calculate|Compose|Examine|Justify|Assess|'
    r'Based on|In about|With reference)\b.+)',
    re.IGNORECASE
)

# Paragraph number at start of a passage line (e.g. "1 Very often" or "6 1 Our")
PARAGRAPH_NUMBER = re.compile(r'^\d+(?:\s+\d+)*\s+(?=[A-Z])')


def _extract_sub_marks(text):

    match = SUBQUESTION_MARKS_PATTERN.search(text)

    if match:
        marks = int(match.group(1))
        text = SUBQUESTION_MARKS_PATTERN.sub("", text).strip()
        return text, marks

    return text, None


def _extract_instruction_marks(text):

    match = INSTRUCTION_MARKS_PATTERN.search(text)

    if match:
        marks = match.group(0)
        text = INSTRUCTION_MARKS_PATTERN.sub("", text).strip()
        return text, marks

    return text, None


def _extract_header_marks(text):

    match = HEADER_MARKS_PATTERN.search(text)

    if match:
        marks = match.group(1)
        text = HEADER_MARKS_PATTERN.sub("", text).strip()
        return text, marks

    return text, None


def analyze_question_block(block):

    lines = block.split("\n")

    header = None
    header_marks = None

    passage_lines = []
    instruction_lines = []

    instruction_marks = None

    subquestions = []

    current_sub = None
    sub_buffer = []

    instruction_mode = False

    for idx, line in enumerate(lines):

        line = line.strip()

        if not line:
            continue

        lower = line.lower()

        # hard stop if new section begins
        if line.startswith("SECTION"):
            break

        # skip alternate visually impaired questions
        if "visually impaired" in lower:
            break

        # HEADER
        if header is None:

            header, header_marks = _extract_header_marks(line)

            # Check if header continues on the next line
            # A continuation line must be short and not look like passage content
            if header and not header.rstrip().endswith(('.', '?', '!', ':')):
                for next_idx in range(idx + 1, len(lines)):
                    next_line = lines[next_idx].strip()
                    if not next_line:
                        continue
                    # Don't merge if it's a subquestion, passage paragraph start,
                    # or a long line (likely content, not a header fragment)
                    is_subquestion = SUBQUESTION_PATTERN.match(next_line)
                    is_paragraph_start = re.match(r'^\d+\s+[A-Z]', next_line)
                    is_long = len(next_line) > 50
                    if not is_subquestion and not is_paragraph_start and not is_long:
                        header_combined = header + " " + next_line
                        header_combined, header_marks = _extract_header_marks(header_combined)
                        header = header_combined
                        lines[next_idx] = ""
                    break

            continue

        # SUBQUESTION START
        if SUBQUESTION_PATTERN.match(line):

            instruction_mode = False

            if current_sub:

                text = " ".join(sub_buffer).strip()
                text, marks = _extract_sub_marks(text)

                subquestions.append({
                    "label": current_sub,
                    "text": text,
                    "marks": marks
                })

            label = line.split(")")[0] + ")"
            current_sub = label

            content = line[len(label):].strip()
            sub_buffer = [content]

            continue

        # CONTINUE SUBQUESTION
        if current_sub:
            sub_buffer.append(line)
            continue

        # DETECT INSTRUCTION
        if INSTRUCTION_STARTER.match(line) and not instruction_mode:

            instruction_mode = True
            instruction_lines.append(line)
            continue

        # CONTINUE INSTRUCTION
        if instruction_mode:

            instruction_lines.append(line)
            continue

        # OTHERWISE PASSAGE
        passage_lines.append(line)

    # flush last subquestion
    if current_sub:

        text = " ".join(sub_buffer).strip()
        text, marks = _extract_sub_marks(text)

        subquestions.append({
            "label": current_sub,
            "text": text,
            "marks": marks
        })

    # Join passage lines, preserving paragraph boundaries.
    # Lines beginning with a paragraph number start a new paragraph.
    passage_parts = []
    for pl in passage_lines:
        if passage_parts and PARAGRAPH_NUMBER.match(pl):
            passage_parts.append("\n\n" + pl)
        else:
            if passage_parts:
                passage_parts.append(" " + pl)
            else:
                passage_parts.append(pl)

    passage = "".join(passage_parts).strip()

    instruction = " ".join(instruction_lines).strip() if instruction_lines else None

    # If no explicit instruction was found, check if one is embedded in the
    # passage text after a sentence boundary (e.g. "...success. Draft a formal...")
    if not instruction and passage:
        m = EMBEDDED_INSTRUCTION.search(passage)
        if m:
            split_pos = m.start(2)
            instruction = passage[split_pos:].strip()
            passage = passage[:m.start(2)].strip()
            # keep the sentence-ending punctuation on the passage
            if not passage.endswith(('.', '!', '?')):
                passage = passage + m.group(1)

    if instruction:
        instruction, instruction_marks = _extract_instruction_marks(instruction)

    # Flag subquestions with missing/truncated text (PDF extraction failures)
    for sq in subquestions:
        sq["incomplete"] = not sq["text"] or len(sq["text"].strip()) < 3

    return {
        "header": header,
        "header_marks": header_marks,
        "passage": passage,
        "instruction": instruction,
        "instruction_marks": instruction_marks,
        "subquestions": subquestions
    }