# `scripts/run_all_separate.py`

## Overview
[`scripts/run_all_separate.py`](file:///Users/kartiksirohi/FinAbstain/scripts/run_all_separate.py) coordinates multi-report dataset generation across diverse industry sectors. It executes the FinAbstain pipeline independently for each company filing (`amzn`, `cat`, `pfe`, `ko`), maintains isolated working directories (`out/{report_id}/`), and consolidates all generated items into unified combined benchmark files and a final release package.

---

## How It Works

1. **Company Filing Catalog (`REPORTS`)**:
   Defines target filings with industry sectors, anonymization pseudonyms, candidate quotas, and final targets:
   - **`amzn`**: Amazon.com, Inc. (E-Commerce / Cloud) $\to$ *Aldervane Holdings* (12 candidates, 8 final)
   - **`cat`**: Caterpillar Inc. (Industrial / Heavy Machinery) $\to$ *Vanguard Heavy Industries* (20 candidates, 15 final)
   - **`pfe`**: Pfizer Inc. (Pharmaceuticals / BioTech) $\to$ *Aethelgard Therapeutics* (25 candidates, 20 final)
   - **`ko`**: The Coca-Cola Company (Consumer Staples / Beverages) $\to$ *Apex Refreshment Brands* (25 candidates, 20 final)
2. **Individual Execution**:
   - For each report, checks if `out/{report_id}/08_benchmark.jsonl` already exists.
   - If missing, launches `pipeline.py` via `subprocess.run` with parameters tailored to that filing.
3. **Consolidation**:
   - Gathers benchmark records from all individual report directories.
   - Copies clean raw texts and anonymized texts to `release/reports/raw/` and `release/reports/anonymized/`.
   - Stably sorts all items by `id`.
   - Writes consolidated `out/combined/benchmark.jsonl` and `release/benchmark.jsonl`.
4. **Dataset Card & Reporting**:
   - Updates `release/DATASET_CARD.md` with complete cross-filing statistics.
   - Emits a final multi-report summary table to stdout.

---

## Functions Reference

### `run_cmd(cmd: list) -> None`
- **Purpose**: Executes a shell command list with error checking (`check=True`).
- **Parameters**: `cmd` (`list`): List of command tokens.

### `main() -> None`
- **Purpose**: Orchestrates the multi-filing pipeline loop, consolidation, file copy operations, and dataset card creation.

---

## Usage Example

```bash
python scripts/run_all_separate.py
```
