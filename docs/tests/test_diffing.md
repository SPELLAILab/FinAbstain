# `tests/test_diffing.py`

## Overview
[`tests/test_diffing.py`](file:///Users/kartiksirohi/FinAbstain/tests/test_diffing.py) unit tests the deterministic text diff engine implemented in [`src/finabstain/diffing.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/diffing.py).

---

## How It Works

Tests verbatim span deletions, single-anchor insertions, `difflib` sequence verification, and deterministic fallback deletion under various edge cases (not found, multiple matches, valid operations).

---

## Test Functions Reference

### `test_apply_deletion_success() -> None`
- **Purpose**: Verifies clean deletion of a unique sentence span.
- **Assertions**: Error is `None` and deleted sentence is cleanly omitted.

### `test_apply_deletion_not_found() -> None`
- **Purpose**: Verifies that requesting deletion of a non-existent span returns `None` and an informative error message containing `"not found"`.

### `test_apply_deletion_multiple_occurrences() -> None`
- **Purpose**: Verifies that deleting a span that occurs multiple times is safely rejected with `"must be exactly 1"`.

### `test_apply_insertion_success() -> None`
- **Purpose**: Tests that a new sentence is placed on a new line immediately following the anchor line.

### `test_apply_insertion_anchor_not_found() -> None`
- **Purpose**: Tests that an insertion with an invalid anchor returns `None` and `"Anchor not found"`.

### `test_verify_diff_insert() -> None`
- **Purpose**: Verifies that `verify_diff` confirms an insertion diff matches the expected metadata.

### `test_verify_diff_delete() -> None`
- **Purpose**: Verifies that `verify_diff` confirms a deletion diff contains no unexpected changes.

### `test_deterministic_missing_fallback() -> None`
- **Purpose**: Verifies that `deterministic_missing_fallback` accurately identifies lines containing the target answer, excises them, preserves non-answer financial lines, and returns `fallback = True`.

---

## Running the Test

```bash
pytest tests/test_diffing.py -v
```
