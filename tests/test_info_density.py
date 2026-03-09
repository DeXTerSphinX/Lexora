from core.complexity.scorer import compute_complexity


def test_content_word_density_increases():
    simple = "The cat is on the mat."
    dense = "Photosynthesis converts light energy into chemical energy."

    simple_info = compute_complexity(simple)["sentences"][0]["info_density"]
    dense_info = compute_complexity(dense)["sentences"][0]["info_density"]

    assert dense_info > simple_info


def test_named_entity_density_increases():
    simple = "The policy changed."
    entity_dense = "Einstein proposed relativity in Germany."

    simple_info = compute_complexity(simple)["sentences"][0]["info_density"]
    entity_info = compute_complexity(entity_dense)["sentences"][0]["info_density"]

    assert entity_info > simple_info