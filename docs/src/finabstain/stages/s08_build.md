# `src/finabstain/stages/s08_build.py`

## Overview
[`src/finabstain/stages/s08_build.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s08_build.py) implements Stage 8: **Benchmark Dataset Assembly and Long-Context Padding**. It selects the top validated items per category to reach the desired benchmark quota, protects against answer leakage in padding text, constructs long-context ~8,000-token padded contexts using needle-in-a-haystack filler insertion, and creates matching isolated short-context benchmarks.

---

## How It Works

1. **Item Quota Selection**: Groups validated items by category, sorts them by their original candidate rank, and takes the top `final_per_category` items (nominally 25 per category). Warns if shortfalls exist.
2. **Leakage Guard**: Prior to padding, filters the filler pool for each item: any filler section containing the item's `answer`, `conflicting_value`, or `distractor_value` is strictly excluded from that item's haystack.
3. **Padded Context Construction (`construct_padded_context`)**:
   - Randomly samples safe filler sections until cumulative tokens reach the target (e.g. ~8,000 tokens).
   - Inserts the target passage at a random position $p \in [0, 1]$ among the filler sections.
   - Formats each block with explicit headers: `[Section 1]\n...\n\n[Section 2]\n...`.
4. **Benchmark Datasets Output**:
   - `08_benchmark.jsonl`: Full benchmark containing long-context padded contexts (~8,000 tokens).
   - `08_benchmark_short.jsonl`: Identical schema containing only the isolated target passage (~300–500 tokens).
   - Both outputs are stably sorted by item ID.

---

## Functions Reference

### `construct_padded_context(item_text: str, fillers: List[Dict[str, Any]], target_tokens: int, rng: random.Random) -> tuple[str, float, int, int]`
- **Purpose**: Creates an ~8,000-token multi-section context embedding the target passage at a random section index.
- **Parameters**:
  - `item_text` (`str`): The edited passage text.
  - `fillers` (`List[Dict[str, Any]]`): Safe filler sections.
  - `target_tokens` (`int`): Target total token count (e.g., `8000`).
  - `rng` (`random.Random`): Seeded random instance.
- **Returns**: `tuple[str, float, int, int]` containing:
  - `context_str`: Complete formatted context text with section markers.
  - `target_position`: Relative position index ($0.0 \le p \le 1.0$).
  - `target_idx`: 0-indexed section position.
  - `actual_tokens`: Measured token count.

### `run_stage(config: AppConfig, force: bool = False) -> List[Path]`
- **Purpose**: Stage execution entrypoint. Produces `08_benchmark.jsonl` and `08_benchmark_short.jsonl`.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Application config.
  - `force` (`bool`): Re-runs build if `True`.
- **Returns**: `List[Path]`: `[bench_file, short_file]`.

---

## Benchmark Item Record Schema

```json
{
  "id": "fab-amzn-0004-con",
  "category": "conflict",
  "gold_decision": "abstain",
  "gold_reason": "conflict",
  "question": "What was the operating income for fiscal year 2024?",
  "context": "[Section 1]\n...\n\n[Section 7]\n...target passage...",
  "gold_answer": null,
  "original_answer": "$36,874 million",
  "evidence_span": "Operating income was $36,874 million...",
  "fact_type": "amount",
  "report_id": "amzn",
  "section_id": "amzn_sec0004",
  "target_position": 0.4286,
  "target_section_index": 6,
  "approx_tokens": 8140,
  "edit": {
    "anchor": "...",
    "inserted_text": "...",
    "conflicting_value": "$42,500 million"
  },
  "short_value_flag": false,
  "needs_llm_validation": false,
  "validator_a": { ... },
  "validator_b": { ... }
}
```
