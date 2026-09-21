# `src/finabstain/stages/s04_qgen.py`

## Overview
[`src/finabstain/stages/s04_qgen.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s04_qgen.py) implements Stage 4: **Grounded Financial Question-Answer Generation**. Using a generator LLM (e.g. `gemma4:31b`), it prompts the model to generate a factual reading-comprehension question along with its precise answer, verbatim evidence sentence, and fact category from the assigned section text.

---

## How It Works

1. **Prompt Template**: Loads `prompts/qgen.txt` and inserts `{section_text}`. The prompt instructs the model to create an unambiguous question that requires reading the excerpt and cannot be answered by general knowledge.
2. **LLM Generation**: Calls `llm_client.call_chat("generator", ...)` requesting a strict JSON object containing:
   - `question`: The natural-language financial query.
   - `answer`: The concise ground-truth value or figure.
   - `evidence_span`: The verbatim sentence in the section supporting the answer.
   - `fact_type`: Type of financial metric (e.g. `"amount"`, `"percentage"`, `"shares"`, `"date"`).
3. **Deterministic Output Validation**: Validates the model output against strict checks using `validate_qgen_output`.
4. **Resumption Support**: If interrupted, checks existing entries in `out/04_qgen.jsonl` to avoid repeating API calls.
5. **Output**: Writes results to `out/04_qgen.jsonl` and records pass/rejection telemetry in `StatsTracker`.

---

## Functions Reference

### `validate_qgen_output(sec_text: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]`
- **Purpose**: Verifies that the question and answer pair meets quality and grounding criteria.
- **Parameters**:
  - `sec_text` (`str`): The source section text.
  - `data` (`Dict[str, Any]`): Parsed JSON dictionary returned by the generator LLM.
- **Returns**: `Tuple[bool, Optional[str]]`: `(is_valid, failure_reason)`.
- **Validation Rules**:
  - Must contain required fields: `question`, `answer`, `evidence_span`.
  - `evidence_span` must be an exact verbatim substring within `sec_text`.
  - `answer` (or its numerical representation) must be contained within `evidence_span`.
  - The `question` must not leak or contain the `answer`.
  - The `question` must be at least 6 words long and end with `?`.

### `run_stage(config: AppConfig, llm_client: LLMClient, stats: StatsTracker, force: bool = False, limit: Optional[int] = None) -> Path`
- **Purpose**: Executes Stage 4 question generation across all item sections.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Application configuration.
  - `llm_client` ([`LLMClient`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/llm.py#L65-L388)): LLM client instance.
  - `stats` ([`StatsTracker`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stats.py#L13-L110)): Metrics tracker.
  - `force` (`bool`): If `True`, overwrites existing output.
  - `limit` (`Optional[int]`): Max items to process (for debugging).
- **Returns**: `Path`: Path to `out/04_qgen.jsonl`.

---

## JSONL Output Record Schema

```json
{
  "section_id": "amzn_sec0004",
  "category": "conflict",
  "text": "...",
  "question": "What was the total operating income in fiscal 2024?",
  "answer": "$36,874 million",
  "evidence_span": "Operating income was $36,874 million for the fiscal year 2024.",
  "fact_type": "amount",
  "qgen_passed": true
}
```
