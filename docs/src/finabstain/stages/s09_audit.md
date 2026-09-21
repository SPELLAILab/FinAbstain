# `src/finabstain/stages/s09_audit.py`

## Overview
[`src/finabstain/stages/s09_audit.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s09_audit.py) implements Stage 9: **Human Audit Sample Extraction**. It extracts a balanced sample of items across all four categories from the finalized benchmark and formats them into an `audit.csv` spreadsheet ready for blind human inspection and annotation.

---

## How It Works

1. **Source Loading**: Reads items from `08_benchmark_short.jsonl` (or falls back to `08_benchmark.jsonl`).
2. **Stratified Sampling**: Partitions items by category (`answerable`, `missing`, `conflict`, `ambiguous`), shuffles using a seeded RNG, and samples an equal quota from each category to satisfy `config.audit.n_items` (nominally 20 items, 5 per category).
3. **Edit Summaries**: Formats human-readable summaries describing the exact mutation made to the text (e.g., listing deleted spans, inserted conflicting text, or blurred question dimensions).
4. **CSV Generation**: Writes sampled records to `out/audit.csv` with empty columns for `human_label` and `human_notes`.

---

## Functions Reference

### `format_edit_summary(cat: str, edit: Dict[str, Any]) -> str`
- **Purpose**: Converts structured edit dictionary into a concise human-readable string for spreadsheet display.
- **Parameters**:
  - `cat` (`str`): Category.
  - `edit` (`Dict[str, Any]`): Edit metadata dictionary.
- **Returns**: `str`: Readable summary (e.g. `"Deletions: ['Operating income was $36,874M']"`).

### `run_stage(config: AppConfig, force: bool = False) -> Path`
- **Purpose**: Stage execution entrypoint. Generates `out/audit.csv`.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Application config.
  - `force` (`bool`): Re-creates audit CSV if `True`.
- **Returns**: `Path`: Path to `out/audit.csv`.

---

## CSV Output Schema

`out/audit.csv` includes the following header fields:
- `id`: Benchmark item ID (e.g. `fab-amzn-0004-con`).
- `category`: Gold category.
- `question`: Question text.
- `edited_text`: Passage text presented to the evaluator.
- `edit_summary`: Human-readable summary of applied edit.
- `short_value_flag`: Boolean flag indicating if numeric figures were unusually short ($<3$ characters).
- `human_label`: Blank column for human annotator to enter one of: `answerable`, `missing`, `conflict`, `ambiguous`.
- `human_notes`: Blank column for annotator observations.
