from core.complexity.scorer import compute_complexity

def test_rare_words_increase_lexical_score():
    simple = "The cat sat on the mat."
    complex_text = "The mitochondrion facilitates oxidative phosphorylation."

    simple_lex = compute_complexity(simple)["sentences"][0]["lexical"]
    complex_lex = compute_complexity(complex_text)["sentences"][0]["lexical"]

    assert complex_lex > simple_lex