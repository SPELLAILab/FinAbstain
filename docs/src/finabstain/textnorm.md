# `src/finabstain/textnorm.py`

## Overview
[`src/finabstain/textnorm.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/textnorm.py) provides text normalization and financial data extraction utilities used across FinAbstain. It features robust numeric parsing for financial formatting (parenthesized negatives, commas, currency symbols, percentages), token counting (via `tiktoken` with heuristic fallback), reconciliation keyword detection, and numerical equivalence checking.

---

## How It Works

- **Token Counting**: Uses `tiktoken` (`cl100k_base` encoding) when installed, or falls back to an empirical approximation (`words * 1.3`).
- **Text Normalization**: Strips currency symbols (`$`, `€`, `£`), percentage signs, and punctuation; lowercases and collapses multiple spaces.
- **Financial Number Parsing**: Handles accounting conventions where negative numbers are formatted in parentheses like `(1,234.50)` or with leading minus `-1,234.50`.
- **Regex Number Extraction**: Extracts all financial figures from text blocks.
- **Reconciliation Keyword Matching**: Identifies financial words (`restated`, `revised`, `corrected`, `adjusted`, `superseded`) to ensure synthetic contradictory statements in `conflict` edits do not inadvertently reconcile themselves.
- **Answer Presence Detection**: Checks whether a candidate answer is present in a passage using both normalized substring matching and numerical float tolerance matching.

---

## Functions Reference

### `count_tokens(text: str) -> int`
- **Purpose**: Computes token length of a string.
- **Parameters**: `text` (`str`).
- **Returns**: `int`: Number of tokens.

### `normalize_text(text: str) -> str`
- **Purpose**: Standardizes text by lowercasing, stripping punctuation and currency marks, and collapsing whitespace.
- **Parameters**: `text` (`str`).
- **Returns**: `str`: Normalized text string.

### `parse_number_str(s: str) -> Optional[float]`
- **Purpose**: Parses a single numeric string into a float, correctly resolving commas, accounting parentheses `(...)`, and negative signs.
- **Parameters**: `s` (`str`): Input numeric string (e.g., `"(2,700)"`, `"$12.50%"`).
- **Returns**: `Optional[float]`: Parsed float or `None` if invalid.

### `numbers_in(text: str) -> List[float]`
- **Purpose**: Scans a text passage and returns all contained numbers as a list of floats.
- **Parameters**: `text` (`str`).
- **Returns**: `List[float]`: Extracted numbers.

### `relative_diff(val1: float, val2: float) -> float`
- **Purpose**: Computes the relative difference $\frac{|val_1 - val_2|}{\max(|val_1|, |val_2|)}$.
- **Parameters**: `val1` (`float`), `val2` (`float`).
- **Returns**: `float`: Relative difference value.

### `has_reconcile_words(text: str) -> bool`
- **Purpose**: Detects if text contains any accounting reconciliation keywords from `RECONCILE_WORDS` (`restated`, `revised`, `corrected`, `adjusted`, `superseded`, etc.).
- **Parameters**: `text` (`str`).
- **Returns**: `bool`: `True` if any forbidden word is present.

### `answer_in_text(answer: str, text: str) -> bool`
- **Purpose**: Tests if an answer (textual or numeric) exists within a passage.
- **Parameters**:
  - `answer` (`str`): Target answer string.
  - `text` (`str`): Passage to search.
- **Returns**: `bool`: `True` if normalized substring matches or if any numeric value in `answer` matches a numeric value in `text` within a $10^{-4}$ relative difference.

---

## Usage Example

```python
from src.finabstain.textnorm import numbers_in, parse_number_str, answer_in_text

text = "Net loss was ($1,250) million compared to income of $500 million."
nums = numbers_in(text)
assert nums == [-1250.0, 500.0]

assert answer_in_text("-1250", text) is True
```
