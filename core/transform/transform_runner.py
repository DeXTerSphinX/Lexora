"""
Lexora Transformation Runner

Runs transformation pipeline on units produced by the unit builder.

Flow:
unit → complexity analysis → conditional transformation → result

The pipeline is split into two phases so that the SSE streaming
endpoint can yield progress events between scoring and transformation.
"""

from core.complexity.scorer import compute_complexity, get_hard_words
from core.transform import transform_text


TRANSFORMABLE_TYPES = {
    "header",
    "passage",
    "instruction",
    "subquestion"
}


def score_all_units(units):
    """Phase 1: score every unit's complexity. Returns an ordered list of
    result dicts with risk_before populated but not yet transformed."""

    results = [None] * len(units)

    for i, unit in enumerate(units):

        unit_id = unit["id"]
        text = unit.get("text", "")
        marks = unit.get("marks")
        unit_type = unit.get("type")
        incomplete = unit.get("incomplete", False)
        question_number = unit.get("question_number")

        base = {
            "id": unit_id,
            "type": unit_type,
            "marks": marks,
            "question_number": question_number,
        }

        # Empty or incomplete text (PDF extraction failures)
        if not text.strip() or incomplete:

            results[i] = {
                **base,
                "original": text,
                "modified": text,
                "changed": False,
                "risk_before": None,
                "risk_after": None,
                "complexity": None,
            }
            continue

        # Only transform valid text units
        if unit_type not in TRANSFORMABLE_TYPES:

            results[i] = {
                **base,
                "original": text,
                "modified": text,
                "changed": False,
                "risk_before": None,
                "risk_after": None,
                "complexity": None,
            }
            continue

        # Score complexity
        analysis = compute_complexity(text)
        risk_before = analysis["document"]["risk_band"]

        results[i] = {
            **base,
            "original": text,
            "modified": text,
            "changed": False,
            "risk_before": risk_before,
            "risk_after": risk_before,
            "complexity": {
                "sentences": analysis["sentences"],
                "document": analysis["document"],
            },
        }

    return results


def transform_all_units(scored_results):
    """Phase 2: transform HIGH/EXTREME units in-place and add keywords."""

    for r in scored_results:

        text = r["original"]
        risk_before = r["risk_before"]

        # Skip non-scorable units (empty, incomplete, non-transformable)
        if risk_before is None:
            continue

        if risk_before in ["HIGH", "EXTREME"]:

            transformed = transform_text(text)
            modified_text = transformed["modified_text"]
            risk_after = transformed["changes"][0]["risk_after"] if transformed["changes"] else risk_before
            changed = modified_text != text

            r["modified"] = modified_text
            r["risk_after"] = risk_after
            r["changed"] = changed

        r["keywords"] = get_hard_words(r["modified"], n=5)

    return scored_results


def run_transformation(units):
    """Convenience wrapper: score then transform. Produces identical
    output to the original single-pass implementation."""

    scored = score_all_units(units)
    return transform_all_units(scored)
