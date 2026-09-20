import json
import tempfile
from pathlib import Path
import pytest
import numpy as np

from eval.run_eval import validate_dataset_schema, strip_thinking
from eval.score import (
    extract_first_balanced_json,
    normalize_text_for_answer,
    parse_numeric_val,
    compute_answer_em_and_f1,
    parse_model_output,
    compute_metrics_vectorized,
    bootstrap_confidence_intervals,
    compute_baselines,
    evaluate_model_run,
)

def test_validate_dataset_schema_real_benchmark():
    path = Path("release/benchmark.jsonl")
    items, sha = validate_dataset_schema(path)
    assert len(items) == 143
    assert len(sha) == 64
    assert items[0]["source_report"] in {"cat", "amzn", "pfe", "ko", "report"}

def test_validate_dataset_schema_missing_fields():
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl") as f:
        f.write(json.dumps({"id": "123", "category": "answerable"}) + "\n")
        f.flush()
        with pytest.raises(ValueError, match="missing required fields"):
            validate_dataset_schema(Path(f.name))

def test_strip_thinking():
    text_with_think = "<think>Analyzing financial statements...</think>{\"decision\": \"answer\", \"reason\": \"none\", \"answer\": \"$10M\"}"
    clean, appeared = strip_thinking(text_with_think)
    assert appeared is True
    assert "<think>" not in clean
    assert clean.startswith('{"decision"')

    text_no_think = '{"decision": "abstain", "reason": "missing", "answer": ""}'
    clean2, appeared2 = strip_thinking(text_no_think)
    assert appeared2 is False
    assert clean2 == text_no_think

def test_extract_first_balanced_json():
    text = 'Some conversational text: {"decision": "answer", "reason": "none", "nested": {"key": 1}} trailing note.'
    res = extract_first_balanced_json(text)
    assert res is not None
    data = json.loads(res)
    assert data["decision"] == "answer"
    assert data["nested"]["key"] == 1

def test_answer_normalization_and_numeric_parsing():
    assert normalize_text_for_answer("$1,200,000.") == "1200000"
    assert normalize_text_for_answer("(340)") == "-340"
    assert normalize_text_for_answer("12.5 %") == "12.5%"

    assert parse_numeric_val("$1.2 million") == 1200000.0
    assert parse_numeric_val("1.2M") == 1200000.0
    assert parse_numeric_val("3.5 billion") == 3500000000.0
    assert parse_numeric_val("(340)") == -340.0
    assert parse_numeric_val("12.5%") == 12.5

def test_compute_answer_em_and_f1():
    # Numeric equivalence
    em, f1 = compute_answer_em_and_f1("$1.2 million", "1,200,000", "answer")
    assert em == 1.0
    assert f1 > 0.0

    # Substring inclusion
    em2, f12 = compute_answer_em_and_f1("45 million", "the revenue is $45 million in 2024", "answer")
    assert em2 == 1.0

    # Non-answer decision
    em3, f13 = compute_answer_em_and_f1("$100", "$100", "abstain")
    assert em3 == 0.0
    assert f13 == 0.0

def test_parse_model_output_consistency():
    # Valid answer
    rec_valid_ans = {"raw_text": '{"decision": "answer", "reason": "none", "answer": "$50M"}'}
    dec, reas, ans, pf = parse_model_output(rec_valid_ans)
    assert dec == "answer"
    assert reas == "answerable"
    assert ans == "$50M"
    assert pf is False

    # Inconsistent: answer with conflict reason -> parse_fail
    rec_inconsistent = {"raw_text": '{"decision": "answer", "reason": "conflict", "answer": "$50M"}'}
    _, _, _, pf2 = parse_model_output(rec_inconsistent)
    assert pf2 is True

    # Error record -> parse_fail
    rec_err = {"error": "context_overflow", "raw_text": ""}
    _, _, _, pf3 = parse_model_output(rec_err)
    assert pf3 is True

def test_macro_f1_and_metrics_calculation():
    gold = ["answerable", "missing", "conflict", "ambiguous"]
    pred_reasons = ["answerable", "missing", "conflict", "ambiguous"]
    pred_dec = ["answer", "abstain", "abstain", "abstain"]
    gold_ans = ["$10", "", "", ""]
    pred_ans = ["$10", "", "", ""]
    pf = [False] * 4

    m = compute_metrics_vectorized(gold, pred_reasons, pred_dec, gold_ans, pred_ans, pf)
    assert m["reason_macro_f1"] == 1.0
    assert m["decision_accuracy"] == 1.0
    assert m["over_refusal_rate"] == 0.0
    assert m["over_answer_rate"] == 0.0
    assert m["answer_em"] == 1.0
    assert m["parse_fail_rate"] == 0.0

def test_bootstrap_confidence_intervals():
    gold = ["answerable", "missing", "conflict", "ambiguous"] * 10
    pred = ["answerable", "missing", "conflict", "ambiguous"] * 10
    dec = ["answer", "abstain", "abstain", "abstain"] * 10
    ans = ["$10", "", "", ""] * 10
    pf = [False] * 40

    cis = bootstrap_confidence_intervals(gold, pred, dec, ans, ans, pf, seed=42, n_resamples=50)
    assert "reason_macro_f1" in cis
    assert cis["reason_macro_f1"][0] <= cis["reason_macro_f1"][1]
