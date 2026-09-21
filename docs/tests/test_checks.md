# `tests/test_checks.py`

## Overview
[`tests/test_checks.py`](file:///Users/kartiksirohi/FinAbstain/tests/test_checks.py) provides unit test coverage for Stage 6 ([`s06_checks.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s06_checks.py)). It verifies that the deterministic validation suite accurately passes compliant candidate items and flags invalid items across each category.

---

## How It Works

Defines structured item fixtures for `answerable`, `missing`, `conflict`, and `ambiguous` categories, executing `check_item` against both conforming samples and deliberate failure cases (such as retained answers, forbidden reconciliation words, and question answer leaks).

---

## Test Functions Reference

### `test_check_answerable_pass() -> None`
- **Purpose**: Verifies that a valid `answerable` item (unmodified text containing the answer) produces zero failure reasons.

### `test_check_missing_pass_and_fail() -> None`
- **Purpose**: Tests validation rules for `missing` items.
- **Assertions**:
  - Valid deletion item passes with `[]`.
  - Item where the answer is still present in `edited_text` triggers `"still_in_missing_text"`.

### `test_check_conflict_pass_and_fail() -> None`
- **Purpose**: Tests validation rules for `conflict` items.
- **Assertions**:
  - Valid insertion with contradictory figure passes with `[]`.
  - Insertion containing forbidden reconciliation keywords (`revised`, `restated`, etc.) triggers `"reconcile_words"`.

### `test_check_ambiguous_pass_and_fail() -> None`
- **Purpose**: Tests validation rules for `ambiguous` items.
- **Assertions**:
  - Valid distractor insertion and blurred question passes with `[]`.
  - A blurred question that accidentally includes the answer figure triggers `"contains_answer"`.

---

## Running the Test

```bash
pytest tests/test_checks.py -v
```
