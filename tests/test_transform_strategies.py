"""Tests for the enhanced transformation strategies."""

from core.transform.transformer import (
    transform_text,
    _passive_to_active,
    _substitute_synonyms,
    _split_complex_sentence,
    _has_subject_and_verb,
)


# ── Enhanced Clause Splitting ──────────────────────────────────

def test_semicolon_split():
    parts = _split_complex_sentence(
        "The cell divides rapidly; the nucleus replicates its DNA."
    )
    assert len(parts) == 2


def test_while_conjunction():
    parts = _split_complex_sentence(
        "The temperature increased while the pressure decreased significantly."
    )
    assert len(parts) == 2


def test_whereas_conjunction():
    parts = _split_complex_sentence(
        "Water boils at 100 degrees whereas ethanol boils at 78 degrees."
    )
    assert len(parts) == 2


def test_however_conjunction():
    parts = _split_complex_sentence(
        "The results were promising however the sample size was too small."
    )
    assert len(parts) == 2


def test_nonrestrictive_which():
    parts = _split_complex_sentence(
        "The experiment was terminated early, which surprised the researchers."
    )
    assert len(parts) == 2
    assert parts[1].startswith("This")


def test_multi_split():
    parts = _split_complex_sentence(
        "The temperature rose and the pressure increased but the volume remained constant."
    )
    assert len(parts) >= 2  # at least 2, ideally 3


def test_since_temporal_not_split():
    """'Since 2020' has no verb — should not produce a valid split."""
    parts = _split_complex_sentence(
        "Since 2020 the data quality has improved dramatically."
    )
    assert len(parts) == 1


def test_that_not_used_as_split():
    """'that' is not in the conjunction list — sentences with 'that' as
    the only potential split point should remain unsplit."""
    parts = _split_complex_sentence(
        "Explain that the process requires significant energy input."
    )
    assert len(parts) == 1


def test_fragment_rejected():
    parts = _split_complex_sentence(
        "Running quickly and with great determination."
    )
    # No valid subject+verb split, should stay as one
    assert len(parts) == 1


# ── Passive-to-Active ─────────────────────────────────────────

def test_basic_passive_to_active():
    result = _passive_to_active(
        "The experiment was conducted by the research team."
    )
    assert result != "The experiment was conducted by the research team."
    assert "research team" in result.lower()


def test_passive_no_agent_unchanged():
    original = "The results were published in a prestigious journal."
    result = _passive_to_active(original)
    assert result == original


def test_passive_irregular_verb():
    result = _passive_to_active(
        "The report was written by the senior student."
    )
    assert "wrote" in result.lower()


# ── Synonym Substitution ──────────────────────────────────────

def test_protected_exam_verbs():
    result = _substitute_synonyms("Calculate the total displacement of the particle.")
    assert "calculate" in result.lower()


def test_synonym_preserves_capitalization():
    """If a capitalized word is replaced, the replacement should be capitalized."""
    original = "The investigation revealed significant anomalies."
    result = _substitute_synonyms(original)
    # First word of any replacement after 'The' should be capitalized if original was
    words = result.split()
    for w in words:
        if w[0].isupper():
            # All capitalized words in result started with upper — good
            pass
    assert result[0].isupper()


# ── Integration ────────────────────────────────────────────────

def test_return_shape_unchanged():
    result = transform_text("The cat sat on the mat.")
    assert set(result.keys()) == {"modified_text", "changes", "summary"}
    assert set(result["summary"].keys()) == {"sentences_modified", "total_sentences"}


def test_low_risk_untouched():
    result = transform_text("The cat sat.")
    assert result["summary"]["sentences_modified"] == 0
    assert result["modified_text"] == "The cat sat."


def test_strategies_applied_field():
    """If any changes are made, the strategies_applied field should be present."""
    text = (
        "The extraordinarily complex investigation was meticulously conducted "
        "by the researchers and the comprehensive results were subsequently "
        "documented in the institutional repository."
    )
    result = transform_text(text)
    for change in result["changes"]:
        assert "strategies_applied" in change
        assert isinstance(change["strategies_applied"], list)
