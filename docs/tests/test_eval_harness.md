# `tests/test_eval_harness.py`

## Overview
[`tests/test_eval_harness.py`](file:///Users/kartiksirohi/FinAbstain/tests/test_eval_harness.py) tests the evaluation runner and scoring modules ([`eval/run_eval.py`](file:///Users/kartiksirohi/FinAbstain/eval/run_eval.py) and [`eval/score.py`](file:///Users/kartiksirohi/FinAbstain/eval/score.py)).

---

## How It Works

Validates schema constraints on release benchmark datasets, tests regex-based `<think>` block stripping, tests balanced JSON extraction, verifies accounting answer normalization and numeric multiplier parsing, checks parser consistency rules, and tests metric calculation and bootstrap confidence interval generation.

---

## Test Functions Reference

### `test_validate_dataset_schema_real_benchmark() -> None`
- **Purpose**: Validates schema and integrity of the real `release/benchmark.jsonl` dataset.
- **Assertions**: Asserts item count is 143, SHA-256 hash length is 64, and `source_report` matches known filings.

### `test_validate_dataset_schema_missing_fields() -> None`
- **Purpose**: Asserts that datasets missing required schema fields raise `ValueError`.

### `test_strip_thinking() -> None`
- **Purpose**: Verifies that `<think>...</think>` blocks are cleanly removed from completion text and sets `think_stripped = True`.

### `test_extract_first_balanced_json() -> None`
- **Purpose**: Verifies that balanced nested JSON structures containing `"decision"` are isolated from surrounding conversational text.

### `test_answer_normalization_and_numeric_parsing() -> None`
- **Purpose**: Tests accounting text normalization and multiplier expansion (`$1.2 million` $\to 1,200,000$, `(340)` $\to -340$, `12.5%` $\to 12.5$).

### `test_compute_answer_em_and_f1() -> None`
- **Purpose**: Verifies answer EM and token F1 under numeric equivalence, substring inclusion, and non-answer decisions.

### `test_parse_model_output_consistency() -> None`
- **Purpose**: Tests model output parsing rules, ensuring consistent pairs (`answer` with `none`) pass, while inconsistent pairs (`answer` with `conflict`) or error entries are flagged as `PARSE_FAIL`.

### `test_macro_f1_and_metrics_calculation() -> None`
- **Purpose**: Verifies that a perfect prediction set yields 1.0 for Macro-F1, Decision Accuracy, and EM, and 0.0 for over-refusal/over-answer.

### `test_bootstrap_confidence_intervals() -> None`
- **Purpose**: Tests that `bootstrap_confidence_intervals` generates bounded lower and upper confidence limits.

---

## Running the Test

```bash
pytest tests/test_eval_harness.py -v
```
