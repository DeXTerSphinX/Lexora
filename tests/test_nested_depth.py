from core.complexity.scorer import compute_complexity

def test_nested_clause_has_greater_depth_than_flat():
    nested = "The cell, which contains material that regulates division, divides."
    flat = "The cell, which contains material, and which regulates division, divides."

    nested_depth = compute_complexity(nested)["sentences"][0]["depth"]
    flat_depth = compute_complexity(flat)["sentences"][0]["depth"]

    # Nested clause should produce greater structural depth
    assert nested_depth > flat_depth