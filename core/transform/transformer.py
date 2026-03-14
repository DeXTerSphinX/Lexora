"""
Lexora Transformation Pipeline

Uses the complexity engine to identify high-friction sentences
and applies controlled simplifications:

  1. Passive-to-active voice  (structural)
  2. Synonym substitution     (lexical)
  3. Enhanced clause splitting (sentence length)
"""

import re
from typing import Dict, List
from difflib import SequenceMatcher

from nltk.corpus import wordnet
from wordfreq import zipf_frequency
import pyinflect

from core.complexity.scorer import compute_complexity, nlp


# ── Constants ──────────────────────────────────────────────────

SIMILARITY_THRESHOLD = 0.85

CONJUNCTION_PATTERNS = [
    r"\band\b",
    r"\bbut\b",
    r"\bbecause\b",
    r"\balthough\b",
    r"\bwhile\b",
    r"\bwhereas\b",
    r"\bsince\b",
    r"\bhowever\b",
]

PROTECTED_WORDS = {
    "calculate", "describe", "explain", "define", "state", "prove",
    "evaluate", "discuss", "compare", "contrast", "analyze", "analyse",
    "justify", "outline", "identify", "determine", "solve", "derive",
    "sketch", "draw", "label", "list", "name", "classify", "suggest",
    "predict", "estimate", "measure", "examine", "illustrate",
}

SPACY_TO_WORDNET_POS = {
    "NOUN": wordnet.NOUN,
    "VERB": wordnet.VERB,
    "ADJ":  wordnet.ADJ,
    "ADV":  wordnet.ADV,
}

SYNONYM_DIFFICULTY_GAP = 0.5

IRREGULAR_PAST = {
    "written": "wrote", "taken": "took", "given": "gave",
    "shown": "showed", "seen": "saw", "found": "found",
    "made": "made", "done": "did", "known": "knew",
    "begun": "began", "chosen": "chose", "driven": "drove",
    "eaten": "ate", "fallen": "fell", "forgotten": "forgot",
    "frozen": "froze", "gotten": "got", "grown": "grew",
    "hidden": "hid", "proven": "proved", "ridden": "rode",
    "risen": "rose", "spoken": "spoke", "stolen": "stole",
    "sworn": "swore", "thrown": "threw", "understood": "understood",
    "withdrawn": "withdrew", "worn": "wore", "broken": "broke",
    "brought": "brought", "built": "built", "bought": "bought",
    "caught": "caught", "felt": "felt", "held": "held",
    "kept": "kept", "led": "led", "left": "left", "lost": "lost",
    "met": "met", "paid": "paid", "read": "read", "run": "ran",
    "said": "said", "sent": "sent", "set": "set", "sat": "sat",
    "sold": "sold", "spent": "spent", "stood": "stood",
    "taught": "taught", "thought": "thought", "told": "told",
    "won": "won",
}

MAX_SPLIT_DEPTH = 2


# ── Similarity ─────────────────────────────────────────────────

def _semantic_similarity(a: str, b: str) -> float:
    """Lightweight string similarity check."""
    return SequenceMatcher(None, a, b).ratio()


# ── Clause Validation (cached) ─────────────────────────────────

_sv_cache: Dict[str, bool] = {}


def _has_subject_and_verb(text: str) -> bool:
    """Check if a text fragment has both a subject and a verb."""

    if text in _sv_cache:
        return _sv_cache[text]

    doc = nlp(text)

    has_subject = any(t.dep_ in ("nsubj", "nsubjpass") for t in doc)
    has_verb = any(t.pos_ in ("VERB", "AUX") for t in doc)

    result = has_subject and has_verb
    _sv_cache[text] = result
    return result


# ── Strategy 1: Passive-to-Active ──────────────────────────────

def _get_subtree_span(token) -> str:
    """Get the full text of a token's subtree in document order."""
    subtree_tokens = sorted(token.subtree, key=lambda t: t.i)
    return " ".join(t.text for t in subtree_tokens)


def _to_simple_past(verb_token) -> str | None:
    """Convert a past participle to simple past tense."""
    participle = verb_token.text.lower()

    if participle in IRREGULAR_PAST:
        return IRREGULAR_PAST[participle]

    # Regular verbs: past participle == simple past (both end in -ed)
    if participle.endswith("ed"):
        return participle

    return None


def _passive_to_active(sentence: str) -> str:
    """
    Rewrite passive voice to active when an explicit agent exists.
    Returns original sentence if not possible.
    """
    doc = nlp(sentence)

    for token in doc:
        if token.dep_ != "nsubjpass":
            continue

        verb = token.head
        auxpass_token = None
        agent_object = None

        for child in verb.children:
            if child.dep_ == "auxpass":
                auxpass_token = child
            if child.dep_ == "agent":
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        agent_object = grandchild

        # Only rewrite when agent is explicitly present
        if not auxpass_token or not agent_object:
            continue

        active_verb = _to_simple_past(verb)
        if active_verb is None:
            continue

        subject_span = _get_subtree_span(token)
        agent_span = _get_subtree_span(agent_object)

        # Subject moves mid-sentence — lowercase its first char
        if subject_span and subject_span[0].isupper():
            subject_span = subject_span[0].lower() + subject_span[1:]

        # Collect other dependents (not subject, aux, agent, punct)
        exclude_indices = set()
        for t in token.subtree:
            exclude_indices.add(t.i)
        exclude_indices.add(auxpass_token.i)
        for child in verb.children:
            if child.dep_ == "agent":
                for t in child.subtree:
                    exclude_indices.add(t.i)

        other_tokens = []
        for child in sorted(verb.children, key=lambda t: t.i):
            if child.i in exclude_indices or child.dep_ in ("nsubjpass", "auxpass", "agent", "punct"):
                continue
            subtree = sorted(child.subtree, key=lambda t: t.i)
            other_tokens.append(" ".join(t.text for t in subtree if t.pos_ != "PUNCT"))

        other_text = " ".join(other_tokens).strip()

        # Reconstruct: Agent + active verb + subject + rest
        parts = [agent_span, active_verb, subject_span]
        if other_text:
            parts.append(other_text)

        result = " ".join(parts).strip()

        # Preserve original trailing punctuation
        orig_end = sentence.rstrip()[-1] if sentence.rstrip() else ""
        if orig_end in ".!?":
            result = result.rstrip(".!?") + orig_end

        # Capitalize
        if result:
            result = result[0].upper() + result[1:]

        return result

    return sentence


# ── Strategy 2: Synonym Substitution ───────────────────────────

def _word_difficulty(word: str) -> float:
    return max(0.0, 7.0 - zipf_frequency(word.lower(), "en"))


def _find_simpler_synonym(lemma: str, wn_pos, current_difficulty: float, context_vector=None) -> str | None:
    """Find the simplest single-word synonym from WordNet.
    Uses spaCy vector similarity to filter out wrong-sense candidates."""

    candidates = set()

    for synset in wordnet.synsets(lemma, pos=wn_pos):
        for lemma_name in synset.lemma_names():
            if "_" in lemma_name:
                continue
            candidate = lemma_name.lower()
            if candidate == lemma:
                continue
            candidates.add(candidate)

    best = None
    best_difficulty = current_difficulty

    for candidate in candidates:
        # Word-sense disambiguation: reject candidates that are
        # semantically distant from the original word
        if context_vector is not None and context_vector.has_vector:
            candidate_doc = nlp(candidate)
            if candidate_doc.has_vector:
                sim = context_vector.similarity(candidate_doc)
                if sim < 0.4:
                    continue

        d = _word_difficulty(candidate)
        if d < best_difficulty - SYNONYM_DIFFICULTY_GAP:
            best = candidate
            best_difficulty = d

    return best


def _match_morphology(token, replacement: str) -> str:
    """Adjust replacement to match original token's morphological form."""

    if token.pos_ == "NOUN":
        morph = token.morph.get("Number")
        if morph and "Plur" in morph:
            if replacement.endswith(("s", "sh", "ch", "x", "z")):
                return replacement + "es"
            elif replacement.endswith("y") and len(replacement) > 1 and replacement[-2] not in "aeiou":
                return replacement[:-1] + "ies"
            else:
                return replacement + "s"

    if token.pos_ == "VERB":
        # Use pyinflect to conjugate the replacement to match
        # the original verb's tag (VBD, VBG, VBZ, VBN, etc.)
        tag = token.tag_
        repl_doc = nlp(replacement)
        if repl_doc and len(repl_doc) > 0:
            inflected = repl_doc[0]._.inflect(tag)
            if inflected:
                return inflected

    return replacement


def _substitute_synonyms(sentence: str) -> str:
    """Replace hard words with simpler WordNet synonyms."""

    doc = nlp(sentence)
    replacements = []

    for token in doc:
        if token.lemma_.lower() in PROTECTED_WORDS:
            continue
        if token.is_stop or token.is_punct or token.is_space:
            continue
        if len(token.text) <= 3:
            continue

        wn_pos = SPACY_TO_WORDNET_POS.get(token.pos_)
        if wn_pos is None:
            continue

        current_d = _word_difficulty(token.text)
        if current_d <= 2.0:
            continue

        replacement = _find_simpler_synonym(
            token.lemma_.lower(), wn_pos, current_d,
            context_vector=nlp(token.text)
        )
        if replacement is None:
            continue

        replacement = _match_morphology(token, replacement)

        # Preserve capitalization
        if token.text[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]

        replacements.append((token.idx, token.idx + len(token.text), replacement))

    if not replacements:
        return sentence

    # Apply in reverse order to preserve char indices
    result = sentence
    for start, end, repl in sorted(replacements, key=lambda r: -r[0]):
        result = result[:start] + repl + result[end:]

    return result


# ── Strategy 3: Enhanced Clause Splitting ──────────────────────

def _recursive_conjunction_split(text: str, depth: int = 0) -> List[str]:
    """Try each conjunction pattern; recurse on valid halves."""

    if depth >= MAX_SPLIT_DEPTH:
        return [text]

    for pattern in CONJUNCTION_PATTERNS:
        parts = re.split(pattern, text, maxsplit=1)
        if len(parts) == 2:
            first = parts[0].strip()
            second = parts[1].strip()
            if first and second and _has_subject_and_verb(first) and _has_subject_and_verb(second):
                left = _recursive_conjunction_split(first, depth + 1)
                right = _recursive_conjunction_split(second, depth + 1)
                return left + right

    return [text]


def _split_on_nonrestrictive_which(sentence: str) -> List[str]:
    """Split on ', which' when it extends to end of sentence."""

    match = re.search(r",\s*which\b", sentence)
    if not match:
        return [sentence]

    before = sentence[:match.start()].strip()
    after = sentence[match.end():].strip()

    # Only split if clause runs to end (no closing comma = not mid-sentence)
    if "," in after:
        return [sentence]

    second = "This " + after
    if _has_subject_and_verb(before) and _has_subject_and_verb(second):
        return [before, second]

    return [sentence]


def _format_fragment(frag: str) -> str:
    """Capitalize and punctuate a fragment."""
    frag = frag.strip()
    if not frag:
        return frag
    frag = frag[0].upper() + frag[1:]
    if not frag.endswith((".", "!", "?")):
        frag += "."
    return frag


def _split_complex_sentence(sentence: str) -> List[str]:
    """
    Enhanced clause splitter.
    Phases: semicolons → conjunctions → ', which' → format.
    """

    # Phase 1: semicolons
    semi_parts = re.split(r"\s*;\s*", sentence)
    if len(semi_parts) > 1:
        valid = []
        for part in semi_parts:
            part = part.strip()
            if part and _has_subject_and_verb(part):
                valid.append(part)
            elif valid:
                valid[-1] = valid[-1].rstrip(".") + " " + part
            else:
                valid.append(part)
        semi_parts = valid if len(valid) > 1 else [sentence]
    else:
        semi_parts = [sentence]

    # Phase 2: conjunction splitting on each fragment
    conj_parts = []
    for frag in semi_parts:
        conj_parts.extend(_recursive_conjunction_split(frag))

    # Phase 3: non-restrictive ', which'
    final_parts = []
    for part in conj_parts:
        final_parts.extend(_split_on_nonrestrictive_which(part))

    # Phase 4: format
    formatted = [_format_fragment(p) for p in final_parts if p.strip()]

    return formatted if len(formatted) > 1 else [sentence.strip()]


# ── Core Orchestration ─────────────────────────────────────────

def transform_text(text: str) -> Dict:
    """
    Main transformation entry point.

    Applies up to 3 strategies per HIGH/EXTREME sentence:
      1. Passive-to-active voice
      2. Enhanced clause splitting  (biggest score impact — gets priority)
      3. Synonym substitution       (uses remaining similarity budget)
    """

    analysis = compute_complexity(text)
    original_sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    modified_sentences = []
    changes = []

    for i, sent_data in enumerate(analysis["sentences"]):

        sentence_text = original_sentences[i] if i < len(original_sentences) else ""
        risk = sent_data["risk_band"]

        if risk not in {"HIGH", "EXTREME"}:
            modified_sentences.append(sentence_text)
            continue

        current = sentence_text
        applied_strategies = []

        # --- Strategy 1: Passive to active ---
        candidate = _passive_to_active(current)
        if candidate != current:
            sim = _semantic_similarity(sentence_text, candidate)
            if sim >= SIMILARITY_THRESHOLD:
                # Quick check: only accept if it doesn't worsen complexity
                cand_score = compute_complexity(candidate)["document"]["mean_norm"]
                if cand_score <= sent_data["composite_norm"]:
                    current = candidate
                    applied_strategies.append("passive_to_active")

        # --- Strategy 2: Enhanced clause splitting ---
        candidate_parts = _split_complex_sentence(current)
        candidate = " ".join(candidate_parts)
        if candidate != current:
            sim = _semantic_similarity(sentence_text, candidate)
            if sim >= SIMILARITY_THRESHOLD:
                current = candidate
                applied_strategies.append("clause_splitting")

        # --- Strategy 3: Synonym substitution ---
        candidate = _substitute_synonyms(current)
        if candidate != current:
            sim = _semantic_similarity(sentence_text, candidate)
            if sim >= SIMILARITY_THRESHOLD:
                current = candidate
                applied_strategies.append("synonym_substitution")

        # --- Final validation: score must improve ---
        if current != sentence_text:
            new_analysis = compute_complexity(current)
            new_score = new_analysis["document"]["mean_norm"]
            old_score = sent_data["composite_norm"]

            if new_score < old_score:
                modified_sentences.append(current)
                changes.append({
                    "original": sentence_text,
                    "modified": current,
                    "risk_before": risk,
                    "risk_after": new_analysis["document"]["risk_band"],
                    "similarity": _semantic_similarity(sentence_text, current),
                    "strategies_applied": applied_strategies,
                })
            else:
                modified_sentences.append(sentence_text)
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
