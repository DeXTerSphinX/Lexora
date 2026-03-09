from core.transform import transform_text


def test_basic_transformation():
    text = (
        "Explain the process of photosynthesis and describe how chlorophyll absorbs "
        "light energy and converts it into chemical energy within plant cells."
    )

    result = transform_text(text)

    print("\nModified text:\n", result["modified_text"])
    print("\nChanges:\n", result["changes"])
    print("\nSummary:\n", result["summary"])

    assert isinstance(result, dict)
    assert "modified_text" in result
    assert "changes" in result
    assert "summary" in result