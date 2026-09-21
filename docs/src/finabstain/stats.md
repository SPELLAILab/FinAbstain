# `src/finabstain/stats.py`

## Overview
[`src/finabstain/stats.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stats.py) tracks metrics throughout the dataset construction lifecycle. It aggregates pass/rejection counts by stage, records detailed rejection reasons with item contexts, monitors LLM API invocations and cache hits, and computes inter-annotator agreement statistics (including Cohen's kappa) between dual validators.

---

## How It Works

- **Pass & Rejection Logging**: During QGen, Edit, Checks, and Validate stages, failures are reported to `StatsTracker.record_rejection` with exact item IDs, stage names, and error details. Successful items call `StatsTracker.record_pass`.
- **Validation Agreement Computation**: Compares predictions from Validator A and Validator B against gold categories, calculating overall accuracy per validator, mutual agreement rate, both-correct rate, per-category accuracy, and Cohen's kappa using `scikit-learn` if available.
- **Serialization**: Saves summary statistics and detailed rejection logs to `stats.json`.

---

## Classes and Functions Reference

### `class StatsTracker`

#### `__init__(self)`
- **Attributes**:
  - `rejections: List[Dict[str, Any]]` - Full list of recorded rejections.
  - `stage_counts: Dict[str, Dict[str, int]]` - Dictionary tracking `passed` and `rejected` counts per stage.
  - `llm_calls: int` - Total live LLM requests made.
  - `cache_hits: int` - Total requests served from cache.

#### `record_rejection(self, item_id: str, stage: str, reason: str, details: Optional[Dict[str, Any]] = None) -> None`
- **Purpose**: Records a failed candidate item.
- **Parameters**:
  - `item_id` (`str`): Section or item identifier.
  - `stage` (`str`): Name of the stage rejecting the item (e.g. `"s04_qgen"`, `"s06_checks"`).
  - `reason` (`str`): Short error code or descriptive reason.
  - `details` (`Optional[Dict[str, Any]]`): Additional debugging details (such as raw model output).

#### `record_pass(self, stage: str) -> None`
- **Purpose**: Increments the pass counter for the specified stage.
- **Parameters**:
  - `stage` (`str`): Stage identifier.

#### `compute_validation_stats(self, validated_items: List[Dict[str, Any]]) -> Dict[str, Any]`
- **Purpose**: Analyzes stage 7 validation consensus between Validator A and Validator B.
- **Parameters**:
  - `validated_items` (`List[Dict[str, Any]]`): List of items processed by stage 7.
- **Returns**: `Dict[str, Any]` containing:
  - `total_evaluated`: Count of evaluated items.
  - `val_a_accuracy`: Accuracy of Validator A vs gold label.
  - `val_b_accuracy`: Accuracy of Validator B vs gold label.
  - `inter_annotator_agreement`: Agreement rate between A and B ($A == B$).
  - `both_correct_rate`: Proportion where $A == B == \text{gold}$.
  - `cohen_kappa`: Cohen's kappa score (or `None` if `scikit-learn` is absent).
  - `per_category`: Dictionary breaking down accuracy and consensus for each category.

#### `save(self, path: str | Path, extra: Optional[Dict[str, Any]] = None) -> None`
- **Purpose**: Writes accumulated statistics, counts, rejection histories, and any extra metadata to a JSON file.
- **Parameters**:
  - `path` (`str | Path`): Destination path (typically `out/stats.json`).
  - `extra` (`Optional[Dict[str, Any]]`): Supplementary dictionaries (e.g., validation metrics).

---

## Usage Example

```python
from src.finabstain.stats import StatsTracker

stats = StatsTracker()
stats.record_pass("qgen")
stats.record_rejection("item_001", "s06_checks", "diff_verification_failed")
stats.save("out/stats.json")
```
