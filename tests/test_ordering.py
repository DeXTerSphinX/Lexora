from core.complexity.scorer import compute_complexity

def test_easy_less_than_hard():
    easy_text = "The cat sits on the mat."

    hard_text = (
        "The domesticated feline, which was positioned upon the woven textile surface "
        "situated adjacent to the illuminated window, remained stationary."
    )

    easy_score = compute_complexity(easy_text)["document"]["composite_norm"]
    hard_score = compute_complexity(hard_text)["document"]["composite_norm"]

    assert easy_score < hard_score