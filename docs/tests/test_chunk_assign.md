# `tests/test_chunk_assign.py`

## Overview
[`tests/test_chunk_assign.py`](file:///Users/kartiksirohi/FinAbstain/tests/test_chunk_assign.py) tests the document chunking and boilerplate filtering algorithms implemented in Stage 2 ([`s02_chunk.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s02_chunk.py)).

---

## How It Works

- Verifies that `split_into_blocks` partitions text on double newlines and that `merge_blocks_into_sections` groups adjacent blocks within specified word limits.
- Evaluates `is_boilerplate` against standard SEC regulatory patterns and legitimate financial content.

---

## Test Functions Reference

### `test_split_and_merge_blocks() -> None`
- **Purpose**: Checks paragraph block splitting and subsequent greedy block merging.
- **Assertions**:
  - Raw multi-paragraph text splits into 3 distinct blocks.
  - Merging with a maximum word limit of 100 correctly groups them into a single consolidated section.

### `test_boilerplate_detection() -> None`
- **Purpose**: Verifies regex pattern matching for SEC filing boilerplate.
- **Assertions**:
  - `"Item 1. Table of Contents\nPart I"` returns `True`.
  - `"SIGNATURES\nPursuant to the requirements..."` returns `True`.
  - Legitimate financial disclosure `"Total net sales were $637,959 million..."` returns `False`.

---

## Running the Test

```bash
pytest tests/test_chunk_assign.py -v
```
