# `src/finabstain/stages/s05_edit.py`

## Overview
[`src/finabstain/stages/s05_edit.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s05_edit.py) implements Stage 5: **Constrained Synthetic Edit Generation**. It transforms candidate passages according to their assigned category:
- **`answerable`**: Passage remains untouched (verbatim identity).
- **`missing`**: The generator proposes exact span deletions to remove the answer while retaining at least 70% of the original text.
- **`conflict`**: The generator crafts a single contradictory statement and an exact anchor line where it is inserted, ensuring the new figure differs significantly ($\ge 5\%$) and contains no reconciliation words.
- **`ambiguous`**: The generator crafts a distractor fact, selects an anchor line, and blurs a dimension in the original question (e.g., removing a year, period, or segment).

It features a 3-turn interactive retry loop with feedback to correct invalid edits.

---

## How It Works

- **Iterative Refinement Loop**: For `missing`, `conflict`, and `ambiguous`, up to 3 attempts are made. If an attempt fails programmatic checks (e.g. anchor not found, too many words, reconciliation words present), the error is formatted into a user message prompt back to the assistant: `"The edit failed validation: {err}. Please fix it..."`.
- **Category Strategies**:
  - `attempt_missing_edit`: Prompts with `prompts/edit_missing.txt`. Checks that deletions remove the answer, kept word ratio exceeds `min_kept_ratio_missing`, and spans exist uniquely. Falls back to `deterministic_missing_fallback` if all LLM attempts fail.
  - `attempt_conflict_edit`: Prompts with `prompts/edit_conflict.txt`. Requires `anchor`, `inserted_text`, and `conflicting_value`. Verifies word count $\le 60$, absence of reconciliation terms, and numeric relative difference $\ge 0.05$.
  - `attempt_ambiguous_edit`: Prompts with `prompts/edit_ambiguous.txt`. Requires `anchor`, `inserted_text`, `distractor_value`, `blurred_dimension`, `new_question`, and `removed_from_question`. Verifies removed words were truly in the original question and that the new question does not introduce ungrounded novel terms.
- **Output**: Writes updated items to `out/05_edits.jsonl`.

---

## Functions Reference

### `attempt_missing_edit(text: str, question: str, answer: str, template: str, llm_client: LLMClient, stats: StatsTracker, min_kept_ratio: float) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]`
- **Purpose**: Generates and verifies verbatim span deletions to omit the answer.
- **Parameters**: Source text, question, answer, prompt template, LLM client, stats tracker, and minimum retained text ratio.
- **Returns**: `(edited_text, edit_metadata, error_message)`.

### `attempt_conflict_edit(text: str, question: str, answer: str, template: str, llm_client: LLMClient, stats: StatsTracker, max_inserted_words: int, min_rel_diff: float) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]`
- **Purpose**: Generates and applies a contradictory statement at an anchor line.
- **Parameters**: Source text, question, answer, prompt template, LLM client, stats tracker, max word threshold, and minimum numeric difference.
- **Returns**: `(edited_text, edit_metadata, error_message)`.

### `attempt_ambiguous_edit(text: str, question: str, answer: str, template: str, llm_client: LLMClient, stats: StatsTracker, max_inserted_words: int, min_rel_diff: float) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]], Optional[str]]`
- **Purpose**: Generates a distractor fact insertion and a corresponding blurred question.
- **Parameters**: Source text, original question, answer, prompt template, LLM client, stats tracker, max word threshold, and minimum difference.
- **Returns**: `(edited_text, new_question, edit_metadata, error_message)`.

### `run_stage(config: AppConfig, llm_client: LLMClient, stats: StatsTracker, force: bool = False, limit: Optional[int] = None) -> Path`
- **Purpose**: Stage execution entrypoint. Reads `out/04_qgen.jsonl` and produces `out/05_edits.jsonl`.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Pipeline configuration.
  - `llm_client` ([`LLMClient`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/llm.py#L65-L388)): LLM client.
  - `stats` ([`StatsTracker`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stats.py#L13-L110)): Metrics tracker.
  - `force` (`bool`): Re-runs stage if `True`.
  - `limit` (`Optional[int]`): Debugging item limit.
- **Returns**: `Path`: Path to `05_edits.jsonl`.

---

## JSONL Output Record Schema

```json
{
  "section_id": "amzn_sec0004",
  "category": "conflict",
  "text": "...",
  "edited_text": "...\nIn another segment, operating income was reported as $42,500 million.",
  "question": "What was the operating income?",
  "question_final": "What was the operating income?",
  "answer": "$36,874 million",
  "edit": {
    "anchor": "Operating income was $36,874 million...",
    "inserted_text": "In another segment, operating income was reported as $42,500 million.",
    "conflicting_value": "$42,500 million"
  },
  "edit_passed": true
}
```
