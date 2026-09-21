# `src/finabstain/diffing.py`

## Overview
[`src/finabstain/diffing.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/diffing.py) provides the deterministic text mutation engine for FinAbstain. Instead of permitting LLMs to freely rewrite passages (which can introduce hallucinations, style drift, or unintended edits), FinAbstain enforces programmatic, diff-verifiable text modifications:
1. **Verbatim span deletion** (for creating `missing` items).
2. **Single-anchor line insertion** (for introducing `conflict` and `ambiguous` statements).
3. **Diff verification** using Python's `difflib` sequence matching.
4. **Deterministic fallback** for cases where LLM deletions fail.

---

## How It Works

- **Verbatim Span Deletion**: Given a list of target strings to delete, each string must occur *exactly once* in the passage. The function cuts out the target span and cleans up extraneous whitespaces or empty lines.
- **Single-Anchor Line Insertion**: Given an anchor sentence and an insertion string, the engine finds the unique line containing the anchor and inserts the new line directly following it.
- **Diff Verification**: Runs `difflib.SequenceMatcher` between the original passage and edited passage. It asserts that insertion edits contain *only* the expected inserted text block and no other modifications, and deletion edits contain *only* removals.
- **Deterministic Fallback**: If an LLM fails to propose valid span deletions to remove the answer, this fallback splits the text into lines, identifies and removes lines containing the answer, and ensures the kept text meets the minimum length threshold.

---

## Functions Reference

### `clean_whitespace_after_deletion(text: str) -> str`
- **Purpose**: Cleans up internal double spaces and collapses empty lines produced when spans are removed.
- **Parameters**:
  - `text` (`str`): Text string after string replacement.
- **Returns**: `str`: Cleaned text with trimmed lines and single blank line delimiters.

### `apply_deletion(text: str, deletions: List[str]) -> Tuple[Optional[str], Optional[str]]`
- **Purpose**: Applies verbatim span deletions to text with strict singularity validation.
- **Parameters**:
  - `text` (`str`): The original section text.
  - `deletions` (`List[str]`): List of exact substring spans to remove.
- **Returns**:
  - `Tuple[Optional[str], Optional[str]]`: `(edited_text, error_message)`. If any span is missing or appears more than once, returns `(None, error_message)`.

### `apply_insertion(text: str, anchor: str, inserted_text: str) -> Tuple[Optional[str], Optional[str]]`
- **Purpose**: Inserts `inserted_text` on a new line immediately following the line containing `anchor`.
- **Parameters**:
  - `text` (`str`): The original passage text.
  - `anchor` (`str`): A verbatim excerpt from `text` serving as the location anchor.
  - `inserted_text` (`str`): The synthetic sentence to insert.
- **Returns**:
  - `Tuple[Optional[str], Optional[str]]`: `(edited_text, error_message)`. Returns an error if the anchor is empty, missing, or matches multiple locations.

### `verify_diff(original_text: str, edited_text: str, edit_type: str, edit_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]`
- **Purpose**: Formally checks with `difflib` that the edited passage conforms strictly to the expected edit operation.
- **Parameters**:
  - `original_text` (`str`): Text prior to modification.
  - `edited_text` (`str`): Text after modification.
  - `edit_type` (`str`): Edit category (`"answerable"`, `"missing"`, `"conflict"`, `"ambiguous"`).
  - `edit_data` (`Dict[str, Any]`): Dictionary containing edit metadata (`inserted_text`, `deletions`, etc.).
- **Returns**:
  - `Tuple[bool, Optional[str]]`: `(is_valid, error_description)`. Fails if unexpected blocks were inserted, deleted, or replaced.

### `deterministic_missing_fallback(text: str, answer: str, min_kept_ratio: float = 0.70) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]`
- **Purpose**: Programmatic fallback when LLM fails to generate valid deletion spans for a `missing` item.
- **Parameters**:
  - `text` (`str`): Target section text.
  - `answer` (`str`): Answer string or number to excise.
  - `min_kept_ratio` (`float`): Minimum ratio of word count retained (default: `0.70`).
- **Returns**:
  - `Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]`: `(edited_text, edit_metadata, error_message)`.

---

## Usage Example

```python
from src.finabstain.diffing import apply_insertion, apply_deletion, verify_diff

orig = "Total sales were $100M in 2024.\nOperating expenses were $80M."
anchor = "Total sales were $100M in 2024."
ins = "In a footnote, sales were reported as $115M in 2024."

edited, err = apply_insertion(orig, anchor, ins)
ok, diff_err = verify_diff(orig, edited, "conflict", {"inserted_text": ins})
assert ok is True
```
