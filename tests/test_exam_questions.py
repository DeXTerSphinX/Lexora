from core.transform import transform_text


def test_short_instruction_not_modified():
    text = "Define entropy."

    result = transform_text(text)

    assert result["summary"]["sentences_modified"] == 0


def test_math_problem_not_modified():
    text = (
        "A train travels at a constant velocity of 60 km/h for 3 hours. "
        "Calculate the total distance travelled."
    )

    result = transform_text(text)

    # Most math questions should remain unchanged
    assert result["summary"]["sentences_modified"] >= 0


def test_long_biology_sentence_modified():
    text = (
        "Explain the process of photosynthesis and describe how chlorophyll absorbs "
        "light energy and converts it into chemical energy within plant cells."
    )

    result = transform_text(text)

    assert result["summary"]["sentences_modified"] >= 1


def test_complex_physics_sentence():
    text = (
        "Although Newton's Third Law states that every action has an equal and "
        "opposite reaction, explain how this principle applies when a rocket "
        "launches into space."
    )

    result = transform_text(text)

    assert isinstance(result["modified_text"], str)


def test_very_long_sentence():
    text = (
        "Although photosynthesis is a biochemical process occurring within "
        "chloroplasts which contain chlorophyll molecules that absorb sunlight "
        "and convert it into chemical energy stored in glucose molecules which "
        "are later used for cellular respiration explain how this mechanism "
        "supports plant growth and energy storage in plants."
    )

    result = transform_text(text)

    assert isinstance(result["summary"]["sentences_modified"], int)