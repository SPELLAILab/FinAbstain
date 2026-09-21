# `tests/test_build.py`

## Overview
[`tests/test_build.py`](file:///Users/kartiksirohi/FinAbstain/tests/test_build.py) verifies the functionality of Stage 8 ([`s08_build.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s08_build.py)), specifically testing padded context assembly and filler pool leakage protection.

---

## How It Works

- **Padded Context Assembly Test**: Tests that `construct_padded_context` merges filler sections, injects the target passage, formats section headers (`[Section ...]`), and returns a valid relative position ($0.0 \le p \le 1.0$).
- **Leakage Guard Test**: Tests that `answer_in_text` accurately flags filler passages that accidentally contain the target item's answer string, ensuring they are excluded from the padding haystack.

---

## Test Functions Reference

### `test_construct_padded_context() -> None`
- **Purpose**: Verifies that `construct_padded_context` correctly constructs long-context passages.
- **Assertions**:
  - `"[Section"` appears in the generated context.
  - The exact target item text is embedded.
  - `target_pos` is bounded between 0.0 and 1.0.
  - Calculated tokens count is positive.

### `test_leakage_guard_detection() -> None`
- **Purpose**: Tests that answer leakage into filler text is identified.
- **Assertions**:
  - Asserts that a filler text containing `"$637,959"` returns `True` for `answer_in_text`.
  - Asserts that a safe filler text returns `False`.

---

## Running the Test

```bash
pytest tests/test_build.py -v
```
