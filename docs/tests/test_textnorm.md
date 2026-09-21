# `tests/test_textnorm.py`

## Overview
[`tests/test_textnorm.py`](file:///Users/kartiksirohi/FinAbstain/tests/test_textnorm.py) provides unit test coverage for text processing, token estimation, and numerical parsing functions in [`src/finabstain/textnorm.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/textnorm.py).

---

## How It Works

Evaluates each utility function in `textnorm.py` against typical financial strings, testing punctuation stripping, accounting parenthesized negatives, relative difference calculations, and reconciliation keyword detection.

---

## Test Functions Reference

### `test_normalize_text() -> None`
- **Purpose**: Verifies currency symbol removal, lowercasing, and whitespace collapse.
- **Assertions**: `"  Total Net Sales: $574,785 Million! "` normalizes to `"total net sales 574785 million"`.

### `test_parse_number_str() -> None`
- **Purpose**: Tests parsing of formatted financial figures.
- **Assertions**:
  - `"$1,234.50"` $\to 1234.50$
  - `"(500)"` $\to -500.0$
  - `"-45.6"` $\to -45.6$
  - `"not_a_number"` $\to `None`

### `test_numbers_in() -> None`
- **Purpose**: Verifies multi-number extraction from financial statements.
- **Assertions**: Extracts `637959.0`, `-2700.0`, and `19.0` from sample text.

### `test_relative_diff() -> None`
- **Purpose**: Tests relative difference math.
- **Assertions**: Verifies $\frac{|100 - 105|}{105}$ and zero difference for identical numbers.

### `test_has_reconcile_words() -> None`
- **Purpose**: Tests detection of accounting reconciliation words.
- **Assertions**:
  - Detects `"restated"` and `"revised"`.
  - Asserts normal growth sentences return `False`.

### `test_answer_in_text() -> None`
- **Purpose**: Tests textual and numeric answer matching.
- **Assertions**: Confirms presence of `"$53,200 million"` and `"53200"` in passage text, while rejecting unrelated numbers.

### `test_count_tokens() -> None`
- **Purpose**: Verifies that `count_tokens` returns a positive integer for non-empty text.

---

## Running the Test

```bash
pytest tests/test_textnorm.py -v
```
