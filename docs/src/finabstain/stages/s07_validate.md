# `src/finabstain/stages/s07_validate.py`

## Overview
[`src/finabstain/stages/s07_validate.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s07_validate.py) implements Stage 7: **Dual-Model Independent Blind Validation**. To ensure high benchmark label quality, every passed item is independently evaluated by two distinct frontier models (`validator_a` and `validator_b`, e.g., `gpt-oss:120b` and `nemotron-3-super`). Both models classify the passage under zero-shot blind instructions without knowing the intended gold category. Only items where **both models achieve full consensus with the gold category** are retained.

---

## How It Works

1. **Prompt Construction**: Merges the official abstention taxonomy definitions (`prompts/taxonomy.txt`) with the evaluation template (`prompts/validate.txt`), embedding `{question}` and `{section_text}` (`edited_text`).
2. **Blind Evaluation**:
   - Invocations are zero-shot and blind; the models do not receive the target category.
   - Invokes `Validator A` via `llm_client.call_chat("validator_a", ...)`.
   - Invokes `Validator B` via `llm_client.call_chat("validator_b", ...)`.
3. **Consensus Gating**:
   - Extracts predicted labels (`label_a`, `label_b`).
   - `validated = (label_a == gold_cat and label_b == gold_cat)`.
   - If either validator disagrees with the gold category or with each other, the candidate item is rejected.
4. **Validation Telemetry**: Computes inter-annotator agreement metrics and Cohen's kappa via `stats.compute_validation_stats` and updates `out/stats.json`.
5. **Output**: Writes results to `out/07_validated.jsonl`.

---

## Functions Reference

### `run_stage(config: AppConfig, llm_client: LLMClient, stats: StatsTracker, force: bool = False, limit: Optional[int] = None) -> Path`
- **Purpose**: Executes dual validation across all checked candidates.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Pipeline configuration.
  - `llm_client` ([`LLMClient`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/llm.py#L65-L388)): LLM client.
  - `stats` ([`StatsTracker`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stats.py#L13-L110)): Metrics tracker.
  - `force` (`bool`): If `True`, re-runs validation.
  - `limit` (`Optional[int]`): Max items to process.
- **Returns**: `Path`: Path to `out/07_validated.jsonl`.

---

## JSONL Output Record Schema

```json
{
  "section_id": "amzn_sec0004",
  "category": "conflict",
  "validated": true,
  "needs_llm_validation": false,
  "validator_a": {
    "model": "gpt-oss:120b",
    "label": "conflict",
    "answer": "",
    "rationale": "The passage contains two contradictory values for operating income: $36,874M and $42,500M."
  },
  "validator_b": {
    "model": "nemotron-3-super",
    "label": "conflict",
    "answer": "",
    "rationale": "Conflicting metrics are reported for operating income without reconciliation."
  }
}
```
