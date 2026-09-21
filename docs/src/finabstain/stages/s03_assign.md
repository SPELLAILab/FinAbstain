# `src/finabstain/stages/s03_assign.py`

## Overview
[`src/finabstain/stages/s03_assign.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s03_assign.py) implements Stage 3: **Feasibility Verification, Category Assignment, and Filler Pool Allocation**. It checks that a sufficient volume of eligible sections and filler text exists to meet target benchmark sizes, round-robin assigns target items across the four benchmark categories (`answerable`, `missing`, `conflict`, `ambiguous`), and segregates remaining passages into the long-context filler pool.

---

## How It Works

1. **Deterministic Ordering**: Reads and sorts sections from `02_sections.jsonl` by `section_id` to guarantee reproducible assignment across runs.
2. **Feasibility Validation**:
   - Checks that eligible sections count is at least $4 \times \text{candidates\_per\_category}$. If not, raises a helpful `RuntimeError` prompting the user to supply more filing data.
   - Calculates total tokens available in the filler pool (sections with $\ge 80$ words) and ensures it contains at least $1.5 \times$ the maximum target padding tokens (e.g. $\ge 12,000$ tokens for 8,000-token padding).
3. **Round-Robin Assignment**:
   - Randomly shuffles eligible sections with a seeded RNG.
   - Takes the first $4 \times \text{candidates\_per\_category}$ sections and assigns categories round-robin:
     - Index 0: `answerable` (rank 0)
     - Index 1: `missing` (rank 0)
     - Index 2: `conflict` (rank 0)
     - Index 3: `ambiguous` (rank 0)
     - Index 4: `answerable` (rank 1), and so on.
4. **Filler Pool Designation**: Designates remaining eligible sections and non-eligible sections ($\ge 80$ words) as `role = "filler"`.
5. **Output**: Writes assigned records to `out/03_assigned.jsonl`.

---

## Functions Reference

### `run_stage(config: AppConfig, force: bool = False) -> Path`
- **Purpose**: Executes category assignment and filler pool preparation.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Pipeline configuration.
  - `force` (`bool`): If `True`, re-runs assignment even if output exists.
- **Returns**: `Path`: Path to `out/03_assigned.jsonl`.
- **Raises**: `RuntimeError` if section feasibility checks fail.

---

## JSONL Output Record Schema

```json
{
  "section_id": "cat_sec0004",
  "report_id": "cat",
  "index": 4,
  "text": "...",
  "n_words": 310,
  "n_numbers": 6,
  "eligible": true,
  "role": "item",
  "category": "conflict",
  "rank_in_category": 1
}
```
For filler pool entries:
```json
{
  "role": "filler",
  "category": null,
  "rank_in_category": null
}
```
