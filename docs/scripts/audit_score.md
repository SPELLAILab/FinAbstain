# `scripts/audit_score.py`

## Overview
[`scripts/audit_score.py`](file:///Users/kartiksirohi/FinAbstain/scripts/audit_score.py) evaluates human annotations in `out/audit.csv` against gold benchmark labels. It calculates overall human agreement accuracy, reports per-category accuracy breakdowns, and details any disagreements between human evaluators and the benchmark ground truth.

---

## How It Works

1. **CSV Ingestion**: Reads `out/audit.csv` (or a path passed via CLI argument).
2. **Annotation Tracking**: Identifies rows where `human_label` has been completed.
3. **Accuracy & Consensus Calculation**:
   - Calculates overall agreement rate $\frac{\text{correct\_count}}{\text{filled\_rows}}$.
   - Calculates per-category agreement rates (`answerable`, `missing`, `conflict`, `ambiguous`).
4. **Disagreement Logging**: For any item where the human annotator diverged from the gold label, extracts and prints the Item ID, Gold Label, Human Label, Question, and Human Notes.

---

## Functions Reference

### `score_audit(csv_path: Path) -> None`
- **Purpose**: Parses, scores, and prints the audit evaluation report to stdout.
- **Parameters**:
  - `csv_path` (`Path`): Path to the filled `audit.csv` file.
- **Behavior**:
  - Exits with code 1 if file does not exist.
  - Informs the user if no rows have been annotated yet.
  - Prints formatted agreement percentages and disagreement details.

### `main() -> None`
- **Purpose**: CLI entrypoint. Takes `sys.argv[1]` as target CSV path, defaulting to `out/audit.csv`.

---

## Usage Example

```bash
# Score default audit CSV
python scripts/audit_score.py

# Score specific company audit CSV
python scripts/audit_score.py out/cat/audit.csv
```
