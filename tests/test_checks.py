from src.finabstain.config import AppConfig
from src.finabstain.stages.s06_checks import check_item

def test_check_answerable_pass():
    cfg = AppConfig()
    item = {
        "edit_passed": True,
        "category": "answerable",
        "text": "Net income was $50 million.",
        "edited_text": "Net income was $50 million.",
        "question": "What was the net income?",
        "question_final": "What was the net income?",
        "answer": "$50 million",
        "edit": {},
    }
    reasons = check_item(item, cfg, set())
    assert reasons == []

def test_check_missing_pass_and_fail():
    cfg = AppConfig()
    # Pass
    long_prefix = "The company reported extensive financial results across operations in the region.\n"
    item_pass = {
        "edit_passed": True,
        "category": "missing",
        "text": f"{long_prefix}Net income was $50 million.\nFooter info detailing secondary operations.",
        "edited_text": f"{long_prefix}Footer info detailing secondary operations.",
        "question": "What was the net income?",
        "question_final": "What was the net income?",
        "answer": "$50 million",
        "edit": {"deletions": ["Net income was $50 million."]},
    }
    assert check_item(item_pass, cfg, set()) == []

    # Fail: answer still in text
    item_fail = dict(item_pass)
    item_fail["edited_text"] = "Header info.\nNet income was $50 million."
    reasons = check_item(item_fail, cfg, set())
    assert any("still_in_missing_text" in r for r in reasons)

def test_check_conflict_pass_and_fail():
    cfg = AppConfig()
    text = "Revenues were $100 million."
    ins = "In a footnote, revenues were stated as $120 million."
    edited = f"{text}\n{ins}"
    item_pass = {
        "edit_passed": True,
        "category": "conflict",
        "text": text,
        "edited_text": edited,
        "question": "What were the revenues?",
        "question_final": "What were the revenues?",
        "answer": "$100 million",
        "edit": {
            "anchor": text,
            "inserted_text": ins,
            "conflicting_value": "$120 million",
        },
    }
    assert check_item(item_pass, cfg, set()) == []

    # Fail: reconcile words present
    item_fail_recon = dict(item_pass)
    ins_recon = "Revenues were revised to $120 million."
    item_fail_recon["edited_text"] = f"{text}\n{ins_recon}"
    item_fail_recon["edit"] = {
        "anchor": text,
        "inserted_text": ins_recon,
        "conflicting_value": "$120 million",
    }
    reasons = check_item(item_fail_recon, cfg, set())
    assert any("reconcile_words" in r for r in reasons)

def test_check_ambiguous_pass_and_fail():
    cfg = AppConfig()
    text = "For 2024, revenues were $100 million."
    ins = "For 2023, revenues were $80 million."
    edited = f"{text}\n{ins}"
    item_pass = {
        "edit_passed": True,
        "category": "ambiguous",
        "text": text,
        "edited_text": edited,
        "question": "For 2024, what were the revenues?",
        "question_final": "What were the revenues?",
        "answer": "$100 million",
        "edit": {
            "anchor": text,
            "inserted_text": ins,
            "distractor_value": "$80 million",
            "blurred_dimension": "period",
            "removed_from_question": ["For", "2024,"],
        },
    }
    assert check_item(item_pass, cfg, set()) == []

    # Fail: question contains answer
    item_fail = dict(item_pass)
    item_fail["question_final"] = "What were the revenues of $100 million?"
    reasons = check_item(item_fail, cfg, set())
    assert any("contains_answer" in r for r in reasons)
