"""
Lexora Transformation Pipeline

Uses the complexity engine to identify high-friction sentences
and applies controlled simplifications.
"""

import re
from typing import Dict, List
from difflib import SequenceMatcher

from core.complexity.scorer import compute_complexity


# ------------------------------------------------------------
# Similarity Utility
# ------------------------------------------------------------

def _semantic_similarity(a: str, b: str) -> float:
    """
    Lightweight semantic similarity approximation.
    """
    return SequenceMatcher(None, a, b).ratio()


# ------------------------------------------------------------
# Sentence Split Operator
# ------------------------------------------------------------

def _split_complex_sentence(sentence: str) -> List[str]:
    """
    Conservative clause splitter.

    Only splits on conjunctions that can form independent clauses.
    Avoids breaking relative clauses like 'that' or 'which'.
    """

    # allowed conjunction splits
    patterns = [
        r"\band\b",
        r"\bbut\b",
        r"\bbecause\b",
        r"\balthough\b"
    ]

    pattern = "|".join(patterns)

    parts = re.split(pattern, sentence, maxsplit=1)

    if len(parts) == 1:
        return [sentence.strip()]

    first = parts[0].strip()
    second = parts[1].strip()

    # Capitalize second clause
    if second:
        second = second[0].upper() + second[1:]

    # Ensure punctuation
    if not first.endswith("."):
        first += "."

    if not second.endswith("."):
        second += "."

    return [first, second]


# ------------------------------------------------------------
# Core Transformation Logic
# ------------------------------------------------------------

def transform_text(text: str) -> Dict:
    """
    Main transformation entry point.
    """

    analysis = compute_complexity(text)

    original_sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    modified_sentences = []
    changes = []

    for i, sent_data in enumerate(analysis["sentences"]):

        sentence_text = original_sentences[i] if i < len(original_sentences) else ""

        risk = sent_data["risk_band"]

        # Only transform HIGH / EXTREME
        if risk not in {"HIGH", "EXTREME"}:
            modified_sentences.append(sentence_text)
            continue

        simplified_parts = _split_complex_sentence(sentence_text)

        simplified_sentence = " ".join(simplified_parts)

        similarity = _semantic_similarity(sentence_text, simplified_sentence)

        if similarity < 0.90:
            modified_sentences.append(sentence_text)
            continue

        new_analysis = compute_complexity(simplified_sentence)

        new_score = new_analysis["document"]["mean_norm"]
        old_score = sent_data["composite_norm"]

        if new_score < old_score:

            modified_sentences.append(simplified_sentence)

            changes.append({
                "original": sentence_text,
                "modified": simplified_sentence,
                "risk_before": risk,
                "risk_after": new_analysis["document"]["risk_band"],
                "similarity": similarity
            })

        else:
            modified_sentences.append(sentence_text)

    modified_text = " ".join(modified_sentences)

    return {
        "modified_text": modified_text,
        "changes": changes,
        "summary": {
            "sentences_modified": len(changes),
            "total_sentences": len(original_sentences)
        }
    }