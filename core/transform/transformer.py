"""
Lexora structural transformation pipeline.

The transformer is intentionally conservative. It only applies rewrites that
can be validated with spaCy dependency parses and always falls back to the
original text when a transformation looks incomplete or uncertain.
"""

import re
from typing import Dict, List, Tuple

import pyinflect

from core.complexity.scorer import (
    SENTENCE_SPLIT_THRESHOLD,
    compute_complexity,
    nlp,
)


MIN_CONFIDENCE = 0.85
CONNECTIVES = {"because", "although", "so", "therefore"}
SUBJECT_DEPS = {"nsubj", "nsubjpass", "csubj", "csubjpass"}
VERB_POS = {"VERB", "AUX"}
STRATEGY_ALIASES = {
    "passive_to_active": "passive_to_active",
    "passive-active": "passive_to_active",
    "passive": "passive_to_active",
    "appositive_separation": "appositive_separation",
    "appositive": "appositive_separation",
    "clause_splitting": "center_embedded_clause_splitting",
    "center_embedded_clause_splitting": "center_embedded_clause_splitting",
    "center_embedded": "center_embedded_clause_splitting",
}
DEFAULT_STRATEGIES = [
    "passive_to_active",
    "appositive_separation",
    "center_embedded_clause_splitting",
]


_sv_cache: Dict[str, bool] = {}


def _sentence_texts(text: str) -> List[str]:
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    return sentences if sentences else [text.strip()] if text.strip() else []


def _token_count(text: str) -> int:
    return sum(1 for token in nlp(text) if not token.is_space and not token.is_punct)


def _has_subject_and_verb(text: str) -> bool:
    candidate = text.strip()
    if not candidate:
        return False
    if candidate in _sv_cache:
        return _sv_cache[candidate]

    doc = nlp(candidate)
    has_subject = any(token.dep_ in SUBJECT_DEPS for token in doc)
    has_verb = any(token.pos_ in VERB_POS for token in doc)
    result = has_subject and has_verb
    _sv_cache[candidate] = result
    return result


def _is_complete_sentence(text: str) -> bool:
    return bool(text and text.strip()) and _has_subject_and_verb(text)


def _format_sentence(text: str, endmark: str = ".") -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = text.strip(" ,;:")
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    if not text.endswith((".", "!", "?")):
        text += endmark
    return text


def _lower_initial(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _subtree_span(token) -> Tuple[int, int]:
    tokens = sorted(token.subtree, key=lambda item: item.i)
    return tokens[0].idx, tokens[-1].idx + len(tokens[-1].text)


def _span_text(text: str, span: Tuple[int, int]) -> str:
    return text[span[0]:span[1]].strip()


def _remove_spans(text: str, spans: List[Tuple[int, int]]) -> str:
    if not spans:
        return text

    result = text
    for start, end in sorted(spans, reverse=True):
        left = result[:start].rstrip()
        right = result[end:].lstrip()

        if left.endswith(",") and (not right or right[0] in ",.!?;:"):
            left = left[:-1].rstrip()
        if right.startswith(","):
            right = right[1:].lstrip()

        joiner = " " if left and right and right[0] not in ".,!?;:" else ""
        result = left + joiner + right

    return re.sub(r"\s+", " ", result).strip()


def _find_agent_object(verb):
    for child in verb.children:
        if child.dep_ != "agent":
            continue
        for grandchild in child.children:
            if grandchild.dep_ in {"pobj", "pcomp"}:
                return grandchild, child
    return None, None


def _active_verb_form(verb, auxpass, agent_object) -> str | None:
    modal = next(
        (child for child in verb.children if child.dep_ == "aux" and child.tag_ == "MD"),
        None,
    )
    if modal is not None:
        base = verb._.inflect("VB") or verb.lemma_
        return f"{modal.text} {base}"

    tag = "VBD"
    if auxpass is not None and auxpass.lemma_.lower() == "be":
        if auxpass.tag_ in {"VBP", "VBZ"}:
            tag = "VBP" if agent_object.morph.get("Number") == ["Plur"] else "VBZ"
        elif auxpass.tag_ == "VBD":
            tag = "VBD"
        elif auxpass.tag_ in {"VB", "VBG"}:
            tag = "VB"

    inflected = verb._.inflect(tag)
    if inflected:
        return inflected

    lemma_doc = nlp(verb.lemma_)
    if lemma_doc:
        return lemma_doc[0]._.inflect(tag) or verb.lemma_
    return None


def _passive_to_active_candidate(sentence: str) -> Tuple[str, float]:
    doc = nlp(sentence)

    for subject in doc:
        if subject.dep_ != "nsubjpass":
            continue

        verb = subject.head
        auxpass = next((child for child in verb.children if child.dep_ == "auxpass"), None)
        agent_object, agent_prep = _find_agent_object(verb)

        if auxpass is None or agent_object is None or agent_prep is None:
            continue

        active_verb = _active_verb_form(verb, auxpass, agent_object)
        if not active_verb:
            continue

        subject_span = _subtree_span(subject)
        agent_span = _subtree_span(agent_object)
        agent_text = _span_text(sentence, agent_span)
        subject_text = _lower_initial(_span_text(sentence, subject_span))
        excluded = set()
        for excluded_root in (subject, auxpass, agent_prep):
            excluded.update(item.i for item in excluded_root.subtree)
        excluded.update(
            child.i
            for child in verb.children
            if child.dep_ == "aux" and child.tag_ == "MD"
        )

        complements = []
        for child in sorted(verb.children, key=lambda item: item.i):
            if child.i in excluded or child.dep_ in {"punct", "aux", "auxpass", "agent", "nsubjpass"}:
                continue
            tokens = [
                item
                for item in sorted(child.subtree, key=lambda item: item.i)
                if item.i not in excluded and not item.is_space and item.dep_ != "punct"
            ]
            if tokens:
                complements.append(" ".join(item.text for item in tokens))

        remaining = " ".join(complements).strip()

        parts = [agent_text, active_verb, subject_text]
        if remaining:
            parts.append(remaining.rstrip(".!?"))

        endmark = sentence.rstrip()[-1] if sentence.rstrip()[-1:] in ".!?" else "."
        candidate = _format_sentence(" ".join(parts), endmark)

        if candidate and candidate != sentence and _is_complete_sentence(candidate):
            return candidate, 0.9

    return sentence, 1.0


def _passive_to_active(sentence: str) -> str:
    transformed, confidence = _passive_to_active_candidate(sentence)
    return transformed if confidence >= MIN_CONFIDENCE else sentence


def _appositive_separation_candidate(sentence: str) -> Tuple[str, float]:
    doc = nlp(sentence)

    for token in doc:
        if token.dep_ != "appos":
            continue

        appos_tokens = list(token.subtree)
        if len(appos_tokens) < 2:
            continue

        appos_span = _subtree_span(token)
        appositive = _span_text(sentence, appos_span).strip(" ,")
        if not appositive:
            continue

        main = _remove_spans(sentence, [appos_span])
        main = _format_sentence(main.rstrip(".!?"))
        first_token = nlp(appositive)[0]
        if first_token.pos_ == "ADJ":
            article = "an" if appositive[0].lower() in "aeiou" else "a"
            second = _format_sentence(f"It is {article} {appositive}")
        else:
            second = _format_sentence(f"It is {appositive}")
        candidate = f"{main} {second}".strip()

        if (
            candidate != sentence
            and _is_complete_sentence(main)
            and _is_complete_sentence(second)
        ):
            return candidate, 0.9

    return sentence, 1.0


def _appositive_separation(sentence: str) -> str:
    transformed, confidence = _appositive_separation_candidate(sentence)
    return transformed if confidence >= MIN_CONFIDENCE else sentence


def _is_list_sentence(doc) -> bool:
    return sum(1 for token in doc if token.dep_ in {"conj", "appos"}) >= 3


def _interrupts_subject_verb(relcl) -> bool:
    head = relcl.head
    root = relcl.sent.root
    subject = next(
        (
            token
            for token in root.subtree
            if token.dep_ in SUBJECT_DEPS and token.head == root
        ),
        None,
    )
    if subject is None:
        subject = next((token for token in relcl.sent if token.dep_ in SUBJECT_DEPS), None)

    return subject is not None and subject.i <= head.i < relcl.i and relcl.i < root.i


def _relative_clause_sentence(relcl, anchor_text: str) -> str:
    clause_tokens = sorted(relcl.subtree, key=lambda token: token.i)
    clause_text = " ".join(token.text for token in clause_tokens if not token.is_space)
    clause_text = re.sub(r"\s+([,.!?;:])", r"\1", clause_text)

    words = clause_text.split()
    if words and words[0].lower() in {"who", "which", "that"}:
        words = words[1:]
    clause_text = " ".join(words).strip(" ,")

    first = words[0].lower() if words else ""
    if first in CONNECTIVES:
        return _format_sentence(f"{first.capitalize()} {anchor_text} {' '.join(words[1:])}")
    return _format_sentence(f"{anchor_text} {clause_text}")


def _center_embedded_clause_split_candidate(sentence: str) -> Tuple[str, float]:
    if _token_count(sentence) <= SENTENCE_SPLIT_THRESHOLD:
        return sentence, 1.0

    doc = nlp(sentence)
    sent = next(doc.sents, doc[:])
    if _is_list_sentence(sent):
        return sentence, 1.0

    for relcl in sent:
        if relcl.dep_ != "relcl" or not _interrupts_subject_verb(relcl):
            continue

        relcl_span = _subtree_span(relcl)
        main = _remove_spans(sentence, [relcl_span])
        main = _format_sentence(main.rstrip(".!?"))

        anchor_span = _subtree_span(relcl.head)
        anchor_text = _span_text(sentence, anchor_span).strip(" ,")
        second = _relative_clause_sentence(relcl, anchor_text)
        candidate = f"{main} {second}".strip()

        if (
            candidate != sentence
            and _is_complete_sentence(main)
            and _is_complete_sentence(second)
        ):
            return candidate, 0.88

    return sentence, 1.0


def _split_complex_sentence(sentence: str) -> List[str]:
    transformed, confidence = _center_embedded_clause_split_candidate(sentence)
    if confidence < MIN_CONFIDENCE or transformed == sentence:
        return [sentence]
    return _sentence_texts(transformed)


def _normalize_strategies(strategies: list) -> List[str]:
    if not strategies:
        return DEFAULT_STRATEGIES[:]

    normalized = []
    for strategy in strategies:
        name = STRATEGY_ALIASES.get(str(strategy).strip().lower())
        if name and name not in normalized:
            normalized.append(name)
    return normalized


def _apply_strategy(sentence: str, strategy: str) -> Tuple[str, float]:
    if strategy == "passive_to_active":
        return _passive_to_active_candidate(sentence)
    if strategy == "appositive_separation":
        return _appositive_separation_candidate(sentence)
    if strategy == "center_embedded_clause_splitting":
        return _center_embedded_clause_split_candidate(sentence)
    return sentence, 1.0


def transform_unit(text: str, strategies: list) -> dict:
    original = text if text is not None else ""
    selected = _normalize_strategies(strategies)
    sentences = _sentence_texts(original)

    if not sentences:
        return {
            "original": original,
            "transformed": original,
            "transformations_applied": [],
            "confidence": 1.0,
        }

    transformed_sentences = []
    applied = []
    confidences = []

    for sentence in sentences:
        current = sentence
        sentence_applied = []
        sentence_confidences = []

        for strategy in selected:
            candidate, confidence = _apply_strategy(current, strategy)
            if (
                confidence >= MIN_CONFIDENCE
                and candidate
                and candidate.strip()
                and candidate != current
                and all(_is_complete_sentence(part) for part in _sentence_texts(candidate))
            ):
                current = candidate
                sentence_applied.append(strategy)
                sentence_confidences.append(confidence)

        transformed_sentences.append(current if current.strip() else sentence)
        applied.extend(sentence_applied)
        confidences.extend(sentence_confidences)

    result_text = " ".join(transformed_sentences).strip() or original
    confidence = min(confidences) if confidences else 1.0

    if confidence < MIN_CONFIDENCE or not result_text:
        result_text = original
        applied = []
        confidence = 1.0

    return {
        "original": original,
        "transformed": result_text,
        "transformations_applied": applied,
        "confidence": float(confidence),
    }


def transform_text(text: str) -> Dict:
    """
    Backwards-compatible wrapper for older callers.

    New code should prefer transform_unit(text, strategies), but keeping this
    shape avoids breaking the existing package import surface.
    """
    result = transform_unit(text, DEFAULT_STRATEGIES)
    changed = result["transformed"] != result["original"]
    changes = []

    if changed:
        changes.append({
            "original": result["original"],
            "modified": result["transformed"],
            "risk_before": compute_complexity(result["original"])["document"]["risk_band"],
            "risk_after": compute_complexity(result["transformed"])["document"]["risk_band"],
            "confidence": result["confidence"],
            "strategies_applied": result["transformations_applied"],
        })

    return {
        "modified_text": result["transformed"],
        "changes": changes,
        "summary": {
            "sentences_modified": len(changes),
            "total_sentences": len(_sentence_texts(text)),
        },
    }
