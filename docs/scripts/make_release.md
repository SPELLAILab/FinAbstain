# `scripts/make_release.py`

## Overview
[`scripts/make_release.py`](file:///Users/kartiksirohi/FinAbstain/scripts/make_release.py) packages generated benchmark artifacts from the pipeline output folder (`out/`) into the standardized `release/` directory. It copies the benchmark files, telemetry logs, and generates an automated `DATASET_CARD.md` describing dataset statistics, category distributions, and methodology.

---

## How It Works

1. **Artifact Duplication**:
   - Copies `out/08_benchmark.jsonl` $\to$ `release/benchmark.jsonl`.
   - Copies `out/08_benchmark_short.jsonl` $\to$ `release/benchmark_short.jsonl`.
   - Copies `out/stats.json` $\to$ `release/stats.json`.
   - Copies `out/run_manifest.json` $\to$ `release/run_manifest.json`.
2. **Benchmark Distribution Analysis**:
   - Reads `benchmark.jsonl`.
   - Analyzes counts per category (`answerable`, `missing`, `conflict`, `ambiguous`).
   - Analyzes decisions (`answer` vs `abstain`).
   - Computes average token length across contexts.
3. **Dataset Card Generation**:
   - Programmatically formats a GitHub-flavored Markdown document `DATASET_CARD.md`.
   - Incorporates category definitions, dual-validation methodology, leakage guard descriptions, and MIT licensing information.

---

## Functions Reference

### `make_release(out_dir_str: str = "out", release_dir_str: str = "release") -> None`
- **Purpose**: Copies generated pipeline files to the release folder and writes `DATASET_CARD.md`.
- **Parameters**:
  - `out_dir_str` (`str`): Source pipeline directory (default: `"out"`).
  - `release_dir_str` (`str`): Destination release directory (default: `"release"`).

### `main` block
- Invokes `make_release()` when run directly as a script.

---

## Usage Example

```bash
python scripts/make_release.py
```
