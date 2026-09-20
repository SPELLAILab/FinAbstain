from src.finabstain.textnorm import (
    normalize_text,
    parse_number_str,
    numbers_in,
    relative_diff,
    has_reconcile_words,
    answer_in_text,
    count_tokens,
)

def test_normalize_text():
    assert normalize_text("  Total Net Sales: $574,785 Million! ") == "total net sales 574785 million"
    assert normalize_text("Operating margin: 30.6%") == "operating margin 306"

def test_parse_number_str():
    assert parse_number_str("$1,234.50") == 1234.50
    assert parse_number_str("(500)") == -500.0
    assert parse_number_str("-45.6") == -45.6
    assert parse_number_str("not_a_number") is None

def test_numbers_in():
    text = "Net sales were $637,959 million, compared with an operating loss of ($2,700) million and margin of 19%."
    nums = numbers_in(text)
    assert 637959.0 in nums
    assert -2700.0 in nums
    assert 19.0 in nums

def test_relative_diff():
    assert relative_diff(100.0, 105.0) == 0.05 / 1.05
    assert relative_diff(100.0, 100.0) == 0.0

def test_has_reconcile_words():
    assert has_reconcile_words("The amounts were restated following the audit.") is True
    assert has_reconcile_words("Previously reported numbers were revised.") is True
    assert has_reconcile_words("Revenues grew 15% across all segments.") is False

def test_answer_in_text():
    text = "Capital expenditures for the year were $53,200 million."
    assert answer_in_text("$53,200 million", text) is True
    assert answer_in_text("53200", text) is True
    assert answer_in_text("$99,000", text) is False

def test_count_tokens():
    text = "Hello world! This is a test."
    assert count_tokens(text) > 0
