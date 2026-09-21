# `src/finabstain/stages/s06_checks.py`

## Overview
[`src/finabstain/stages/s06_checks.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s06_checks.py) implements Stage 6: **Deterministic Quality and Invariance Checks**. It applies strict, non-LLM Python assertions over every edited item to guarantee dataset integrity before costly multi-model validation.

---

## How It Works

- **Entity Leakage / Residue Detection**: Loads the entity mapping metadata generated in Stage 1 (`{report_id}.mapping.json`). Asserts that no unmasked original entity names appear in `edited_text` or `question_final`.
- **Diff Verification**: Calls `verify_diff` from [`diffing.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/diffing.py#L75-L116) to verify that only the intended modification was made.
- **Answer Leaks**: Ensures the final question does not leak the answer or distractor value.
- **Category-Specific Invariance Rules**:
  - **`answerable`**: Text must be 100% identical to original; answer must exist in text.
  - **`missing`**: Answer must not exist in `edited_text`; retained text ratio must exceed `min_kept_ratio_missing` (nominally 70%).
  - **`conflict`**: Original answer must still be present; `conflicting_value` must be inside inserted text; inserted text must be $\le 60$ words and contain no reconciliation words; relative difference between numbers must be $\ge 5\%$.
  - **`ambiguous`**: Original answer must still be present; `distractor_value` must be in inserted text; no reconciliation words; removed words must have been in the original question; new question cannot introduce novel vocabulary words not present in the original question.
- **Output**: Writes passed and failed items with specific failure reasons to `out/06_checked.jsonl`.

---

## Functions Reference

### `load_anonymization_entities(anon_dir: Path) -> Dict[str, Set[str]]`
- **Purpose**: Loads real company and person entity names from `*.mapping.json` files, filtering out generic business words (`inc`, `statements`, `management`).
- **Parameters**: `anon_dir` (`Path`): Path to anonymized directory (`out/01_anonymized`).
- **Returns**: `Dict[str, Set[str]]`: Map from `report_id` to sets of sensitive entity strings.

### `check_item(item: Dict[str, Any], config: AppConfig, report_entities: Set[str]) -> List[str]`
- **Purpose**: Evaluates all deterministic validation rules against a single candidate item.
- **Parameters**:
  - `item` (`Dict[str, Any]`): Candidate item record from Stage 5.
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Configuration containing thresholds.
  - `report_entities` (`Set[str]`): Set of sensitive entity names for residue checks.
- **Returns**: `List[str]`: List of failure reason codes (empty list if the item passed all checks).

### `run_stage(config: AppConfig, stats: StatsTracker, force: bool = False) -> Path`
- **Purpose**: Stage execution entrypoint. Processes `out/05_edits.jsonl` and produces `out/06_checked.jsonl`.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Application config.
  - `stats` ([`StatsTracker`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stats.py#L13-L110)): Metrics tracker.
  - `force` (`bool`): Recomputes stage if `True`.
- **Returns**: `Path`: Path to `out/06_checked.jsonl`.

---

## JSONL Output Record Schema

```json
{
  "section_id": "cat_sec0004",
  "category": "conflict",
  "passed": true,
  "fail_reasons": []
}
```
If an item failed checks:
```json
{
  "section_id": "cat_sec0004",
  "passed": false,
  "fail_reasons": [
    "conflict_relative_diff_0.021_below_threshold"
  ]
}
```
