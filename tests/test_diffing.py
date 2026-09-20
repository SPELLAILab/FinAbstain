import pytest
from src.finabstain.diffing import (
    apply_deletion,
    apply_insertion,
    verify_diff,
    deterministic_missing_fallback,
)

def test_apply_deletion_success():
    text = "Sentence one.\nSentence two to delete.\nSentence three."
    edited, err = apply_deletion(text, ["Sentence two to delete."])
    assert err is None
    assert edited == "Sentence one.\nSentence three."

def test_apply_deletion_not_found():
    text = "Sentence one.\nSentence two."
    edited, err = apply_deletion(text, ["Nonexistent span"])
    assert edited is None
    assert "not found" in err

def test_apply_deletion_multiple_occurrences():
    text = "Duplicate text.\nMiddle text.\nDuplicate text."
    edited, err = apply_deletion(text, ["Duplicate text."])
    assert edited is None
    assert "must be exactly 1" in err

def test_apply_insertion_success():
    text = "Line 1.\nLine 2 anchor.\nLine 3."
    edited, err = apply_insertion(text, "Line 2 anchor.", "Inserted line here.")
    assert err is None
    lines = edited.split("\n")
    assert lines[0] == "Line 1."
    assert lines[1] == "Line 2 anchor."
    assert lines[2] == "Inserted line here."
    assert lines[3] == "Line 3."

def test_apply_insertion_anchor_not_found():
    text = "Line 1.\nLine 2."
    edited, err = apply_insertion(text, "Missing anchor", "Some text")
    assert edited is None
    assert "Anchor not found" in err

def test_verify_diff_insert():
    text = "Header.\nAnchor sentence.\nFooter."
    inserted = "Conflicting statement."
    edited, _ = apply_insertion(text, "Anchor sentence.", inserted)
    ok, err = verify_diff(text, edited, "conflict", {"inserted_text": inserted})
    assert ok is True
    assert err is None

def test_verify_diff_delete():
    text = "Header.\nDelete me.\nFooter."
    edited, _ = apply_deletion(text, ["Delete me."])
    ok, err = verify_diff(text, edited, "missing", {"deletions": ["Delete me."]})
    assert ok is True
    assert err is None

def test_deterministic_missing_fallback():
    text = "The revenues were $100 million.\nOperating income was $20 million.\nCash was $50 million."
    edited, edit_data, err = deterministic_missing_fallback(text, "$20 million", min_kept_ratio=0.5)
    assert err is None
    assert "$20 million" not in edited
    assert "$100 million" in edited
    assert "$50 million" in edited
    assert edit_data.get("fallback") is True
