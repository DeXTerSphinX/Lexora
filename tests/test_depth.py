from core.complexity.scorer import compute_complexity

def test_subordinate_clause_increases_depth():
    simple = "The cell divides."
    complex_sentence = "The cell, which contains genetic material, divides."

    simple_depth = compute_complexity(simple)["sentences"][0]["depth"]
    complex_depth = compute_complexity(complex_sentence)["sentences"][0]["depth"]

    assert complex_depth > simple_depth