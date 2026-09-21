# `tests/test_pipeline_mock.py`

## Overview
[`tests/test_pipeline_mock.py`](file:///Users/kartiksirohi/FinAbstain/tests/test_pipeline_mock.py) is the end-to-end integration test for the entire FinAbstain dataset generation pipeline. It executes Stages 1 through 9 sequentially using temporary directories and the deterministic mock LLM backend.

---

## How It Works

1. **Test Environment Provisioning**:
   - Uses Pytest's `tmp_path` fixture to provision an isolated sandbox environment (`tmp_path/data/raw`, `tmp_path/out`).
   - Copies fixture text from `tests/fixtures/mini_report.txt` to populate raw report files.
2. **Mock AppConfig Initialization**:
   - Configures `llm.backend = "mock"`.
   - Sets smaller word thresholds (`min_words: 30`, `max_words: 150`) and small item quotas (`candidates_per_category: 1`, `final_per_category: 1`).
3. **End-to-End Stage Execution**:
   - Executes `s01_anonymize.run_stage` through `s09_audit.run_stage`.
   - Asserts the existence and non-emptiness of every intermediate artifact (`01_anonymized/`, `02_sections.jsonl`, `03_assigned.jsonl`, `04_qgen.jsonl`, `05_edits.jsonl`, `06_checked.jsonl`, `07_validated.jsonl`, `08_benchmark.jsonl`, `08_benchmark_short.jsonl`, `audit.csv`).
4. **Final Benchmark Schema Validation**:
   - Inspects generated records in `08_benchmark.jsonl` to ensure all 19 mandatory fields are present and properly formatted.

---

## Test Functions Reference

### `test_full_pipeline_mock(tmp_path) -> None`
- **Purpose**: Runs full 9-stage pipeline from anonymization to audit export against mock LLM responses.
- **Parameters**: `tmp_path`: Built-in Pytest temporary directory fixture.
- **Assertions**:
  - Asserts output file creation for every stage.
  - Verifies that generated benchmark records contain all required keys:
    `id`, `category`, `gold_decision`, `gold_reason`, `question`, `context`, `gold_answer`, `original_answer`, `evidence_span`, `fact_type`, `report_id`, `section_id`, `target_position`, `target_section_index`, `approx_tokens`, `edit`, `short_value_flag`, `needs_llm_validation`, `validator_a`, `validator_b`.

---

## Running the Test

```bash
pytest tests/test_pipeline_mock.py -v
```
