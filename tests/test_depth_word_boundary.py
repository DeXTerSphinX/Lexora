from core.complexity.scorer import compute_complexity

from core.complexity.scorer import compute_complexity

def test_non_clause_word_does_not_artificially_inflate_depth():
    base = "The phenomenon is complex."
    with_word = "The phenomenon of whichness is complex."

    base_depth = compute_complexity(base)["sentences"][0]["depth"]
    word_depth = compute_complexity(with_word)["sentences"][0]["depth"]

    # Adding a noun like 'whichness' should not create large structural jump
    assert abs(word_depth - base_depth) <= 1