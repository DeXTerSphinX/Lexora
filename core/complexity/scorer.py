import spacy
from wordfreq import zipf_frequency

# Load spaCy model once
nlp = spacy.load("en_core_web_md")

# --- Normalization Bounds (calibrated) ---
SENTENCE_MIN = 5.9
SENTENCE_MAX = 21.2

DEPTH_MIN = 2.0
DEPTH_MAX = 8.0

LEXICAL_MIN = 2.3029
LEXICAL_MAX = 3.5996

INFO_MIN = 0.35
INFO_MAX = 0.6046

# --- Dominance Parameters ---
DOMINANCE_THRESHOLD = 0.85
DOMINANCE_BETA = 0.3


def _clamp(value, lower=0.0, upper=1.0):
    return max(lower, min(upper, value))


def _normalize(value, lower_bound, upper_bound):
    if upper_bound == lower_bound:
        return 0.0
    norm = (value - lower_bound) / (upper_bound - lower_bound)
    return _clamp(norm)


def _risk_band(score: float) -> str:
    if score < 0.8:
        return "LOW"
    elif score < 1.6:
        return "MODERATE"
    elif score < 2.6:
        return "HIGH"
    else:
        return "EXTREME"


def _compute_dependency_depth(doc):
    max_depth = 0

    for token in doc:
        depth = 0
        current = token

        while current.head != current:
            depth += 1
            current = current.head

        if depth > max_depth:
            max_depth = depth

    return max_depth


def _compute_lexical_difficulty(doc):
    difficulties = []

    for token in doc:
        if token.is_stop or token.is_punct or token.is_space:
            continue

        word = token.text.lower()
        freq = zipf_frequency(word, "en")
        difficulty = max(0.0, 7.0 - freq)
        difficulties.append(difficulty)

    if not difficulties:
        return 0.0

    return sum(difficulties) / len(difficulties)


def _compute_info_density(sent):
    tokens = [t for t in sent if not t.is_space and not t.is_punct]

    if not tokens:
        return 0.0

    total_tokens = len(tokens)

    content_words = [
        t for t in tokens
        if t.pos_ in {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
    ]

    content_ratio = len(content_words) / total_tokens

    entity_tokens = set()
    for ent in sent.ents:
        for t in ent:
            entity_tokens.add(t.i)

    entity_ratio = len(entity_tokens) / total_tokens

    return 0.7 * content_ratio + 0.3 * entity_ratio


def compute_complexity(text: str, profile: str = "GENERAL") -> dict:
    """
    Complexity scorer v1.0
    - 4 raw metrics
    - 4 normalized metrics
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
        info_density = float(_compute_info_density(sent))

        # --- Normalized values ---
        sentence_norm = _normalize(sentence_length, SENTENCE_MIN, SENTENCE_MAX)
        depth_norm = _normalize(depth, DEPTH_MIN, DEPTH_MAX)
        lexical_norm = _normalize(lexical, LEXICAL_MIN, LEXICAL_MAX)
        info_norm = _normalize(info_density, INFO_MIN, INFO_MAX)

        # --- Base composite ---
        base_composite = (
            sentence_norm +
            depth_norm +
            lexical_norm +
            0.8 * info_norm
        )

        # --- Conditional dominance ---
        max_component = max(
            sentence_norm,
            depth_norm,
            lexical_norm,
            info_norm
        )

        if max_component > DOMINANCE_THRESHOLD:
            base_composite += DOMINANCE_BETA * max_component

        composite_norm = base_composite

        sentence_results.append({
            "lexical": lexical,
            "sentence": sentence_length,
            "depth": depth,
            "info_density": info_density,

            "lexical_norm": lexical_norm,
            "sentence_norm": sentence_norm,
            "depth_norm": depth_norm,
            "info_norm": info_norm,

            "composite_norm": composite_norm,
            "risk_band": _risk_band(composite_norm)
        })

    if sentence_results:
        mean_norm = sum(s["composite_norm"] for s in sentence_results) / len(sentence_results)
        max_norm = max(s["composite_norm"] for s in sentence_results)
    else:
        mean_norm = 0.0
        max_norm = 0.0

    return {
        "sentences": sentence_results,
        "document": {
            "mean_norm": mean_norm,
            "max_norm": max_norm,
            "composite_norm": mean_norm,
            "risk_band": _risk_band(mean_norm)
        }
    }