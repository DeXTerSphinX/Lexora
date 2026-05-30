import spacy
from wordfreq import zipf_frequency

# Load spaCy model once
nlp = spacy.load("en_core_web_md")

# --- Normalization Bounds (calibrated) ---
SENTENCE_MIN = 5.9
SENTENCE_MAX = 28.0
SENTENCE_SPLIT_THRESHOLD = 20

DEPTH_MIN = 2.0
DEPTH_MAX = 8.0

LEXICAL_MIN = 2.3029
LEXICAL_MAX = 3.5996

WORD_LENGTH_MIN = 3.0
WORD_LENGTH_MAX = 8.0

# --- Dominance Parameters ---

def _clamp(value, lower=0.0, upper=1.0):
    return max(lower, min(upper, value))


def _normalize(value, lower_bound, upper_bound):
    if upper_bound == lower_bound:
        return 0.0
    norm = (value - lower_bound) / (upper_bound - lower_bound)
    return _clamp(norm)


def _risk_band(score: float) -> str:
    if score < 0.6:
        return "LOW"
    elif score < 0.9:
        return "MODERATE"
    elif score < 1.3:
        return "HIGH"
    else:
        return "EXTREME"


def _compute_dependency_depth(doc):
    max_depth = 0

    # Detect list-heavy sentences
    # If 3+ tokens have conj or appos dependency,
    # the sentence is a list — cap depth to avoid
    # over-penalising enumeration structures
    list_tokens = [
        t for t in doc 
        if t.dep_ in ("conj", "appos")
    ]
    is_list_heavy = len(list_tokens) >= 3

    for token in doc:
        depth = 0
        current = token

        while current.head != current:
            depth += 1
            current = current.head

        if depth > max_depth:
            max_depth = depth

    # Cap depth for list-heavy sentences
    # Lists look deep in parse trees but aren't
    # cognitively deep for readers
    if is_list_heavy:
        max_depth = min(max_depth, 4)

    return max_depth


def _compute_lexical_difficulty(doc):
    difficulties = []
    word_lengths = [
        len(token.text)
        for token in doc
        if not token.is_punct and not token.is_space
    ]

    for token in doc:
        if token.is_stop or token.is_punct or token.is_space:
            continue

        word = token.text.lower()
        freq = zipf_frequency(word, "en")
        difficulty = max(0.0, 7.0 - freq)
        difficulties.append(difficulty)

    if not difficulties or not word_lengths:
        return 0.0

    zipf_raw = sum(difficulties) / len(difficulties)
    zipf_norm = _normalize(zipf_raw, LEXICAL_MIN, LEXICAL_MAX)
    length_raw = sum(word_lengths) / len(word_lengths)
    length_norm = _normalize(length_raw, WORD_LENGTH_MIN, WORD_LENGTH_MAX)

    return 0.6 * zipf_norm + 0.4 * length_norm


def get_hard_words(text: str, n: int = 5) -> list:
    """
    Return up to n content words with the highest lexical difficulty
    (lowest zipf frequency), preserving original capitalisation.
    Excludes stop words, punctuation, and very short tokens.
    """
    doc = nlp(text)
    seen = set()
    scored = []

    for token in doc:
        if token.is_stop or token.is_punct or token.is_space:
            continue
        if len(token.text) <= 3:
            continue
        word_lower = token.text.lower()
        if word_lower in seen:
            continue
        seen.add(word_lower)
        freq = zipf_frequency(word_lower, "en")
        difficulty = max(0.0, 7.0 - freq)
        if difficulty > 2.0:   # only flag genuinely uncommon words
            scored.append((difficulty, token.text))

    scored.sort(key=lambda x: -x[0])
    return [w for _, w in scored[:n]]


def compute_complexity(text: str, profile: str = "GENERAL") -> dict:
    """
    Complexity scorer v1.0
    - 3 raw metrics
    - 3 normalized metrics
    - Conditional dominance
    - Risk band classification
    """

    doc = nlp(text)

    sentence_results = []

    for sent in doc.sents:
        tokens = [token for token in sent if not token.is_space]

        # --- Raw values ---
        sentence_length = float(len(tokens))
        depth = float(_compute_dependency_depth(sent))
        lexical = float(_compute_lexical_difficulty(sent))

        # --- Normalized values ---
        sentence_norm = _normalize(sentence_length, SENTENCE_MIN, SENTENCE_MAX)
        depth_norm = _normalize(depth, DEPTH_MIN, DEPTH_MAX)
        lexical_norm = lexical

        # --- Base composite ---
        base_composite = (
            1.5 * lexical_norm +
            1.2 * depth_norm +
            0.8 * sentence_norm
        )

        # --- Conditional dominance ---
        composite_norm = base_composite

        sentence_results.append({
            "lexical": lexical,
            "sentence": sentence_length,
            "depth": depth,

            # Frontend-facing keys (explicit names)
            "sentence_length_norm": sentence_norm,
            "dependency_depth_norm": depth_norm,
            "lexical_difficulty_norm": lexical_norm,

            # Legacy keys (backwards compat)
            "lexical_norm": lexical_norm,
            "sentence_norm": sentence_norm,
            "depth_norm": depth_norm,

            "composite_norm": composite_norm,
            "risk_band": _risk_band(composite_norm)
        })

    if sentence_results:
        mean_norm = sum(s["composite_norm"] for s in sentence_results) / len(sentence_results)
        max_norm = max(s["composite_norm"] for s in sentence_results)
        mean_sl = sum(s["sentence_length_norm"] for s in sentence_results) / len(sentence_results)
        mean_dd = sum(s["dependency_depth_norm"] for s in sentence_results) / len(sentence_results)
        mean_ld = sum(s["lexical_difficulty_norm"] for s in sentence_results) / len(sentence_results)
    else:
        mean_norm = max_norm = mean_sl = mean_dd = mean_ld = 0.0

    return {
        "sentences": sentence_results,
        "document": {
            "mean_norm": mean_norm,
            "max_norm": max_norm,
            "composite_norm": mean_norm,
            "risk_band": _risk_band(mean_norm),
            "sentence_length_norm": mean_sl,
            "dependency_depth_norm": mean_dd,
            "lexical_difficulty_norm": mean_ld,
        }
    }
