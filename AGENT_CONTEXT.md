# AGENT_CONTEXT.md: FinAbstain dataset builder

---

## 1. Goal

One command builds a ~100-item benchmark (JSONL) from real financial report text files.

```
python pipeline.py --config config.yaml
```

**What the benchmark tests:** given a long financial-report context and a question, can an LLM decide whether the question is answerable, and if not, say *why*?

**Four categories, 25 items each (balanced):**

| category | gold_decision | gold_reason | meaning |
|---|---|---|---|
| answerable | answer | none | Context contains one unambiguous answer. |
| missing | abstain | missing | Context is on-topic but the needed fact is absent. |
| conflict | abstain | conflict | Context states two different values for the same fact, with nothing to reconcile them. |
| ambiguous | abstain | ambiguous | Question is underspecified: multiple valid answers depending on period/segment/unit/entity the question doesn't name. |

**Scope: dataset creation only.** Evaluation of models is a separate later task, but the output schema (section 8) must contain everything that eval needs.

**Design rules (do not violate):**
1. Items are **independent**: each report section is used for at most one item. No paired variants.
2. Category is assigned to sections by **seeded random shuffle**, never by content.
3. The LLM **never rewrites a whole passage**. It proposes small structured edits; **code applies and verifies them**. Gold labels are true by construction.
4. Everything is **cached, resumable and seeded**. Free-tier quota will run out mid-run, and that must be safe.
5. Only free Ollama Cloud models are used (generation + validation). No paid API in this task.

---

## 2. Models (Ollama Cloud, free tier)

| role | model tag (API name) |
|---|---|
| generator (qgen + edits) | `gemma4:31b` |
| validator A | `gpt-oss:120b` |
| validator B | `nemotron-3-super` |

- These are defaults in `config.yaml`. On startup, list available cloud models (`GET https://ollama.com/api/tags`, fall back to `/v1/models`) and **fail with a clear message listing the available tags** if a configured tag is missing. Tags change often, so never hardcode them outside config.
- API names differ from CLI names: the API uses e.g. `gemma4:31b`, while the CLI/app uses `gemma4:cloud`.
- Auth: header `Authorization: Bearer $OLLAMA_API_KEY`. Base URL `https://ollama.com`. Endpoint `POST /api/chat` with `stream: false`.
- Request options: `temperature: 0`, `seed: <cfg.seed>`, `num_predict` from config (validators need more room, since gpt-oss spends tokens on reasoning; default 2048).
- gpt-oss takes `think: "low"` (a string level, not a bool). Make `think` a per-model config value and omit it when null.
- Ask for JSON with the `format` parameter (JSON schema). Structured output support may vary by model, so the smoke test (section 11) must check it. Fallback: prompt-only JSON, extract the first balanced `{...}`, `json.loads`, retry up to 3 times, then mark the call failed.
- temp 0 is not bit-exact on hosted models. That's fine: the released dataset is the reproducible artifact.

---

## 3. Folder structure

```
finabstain/
├── AGENT_CONTEXT.md          # this file
├── DECISIONS.md              # agent logs choices/assumptions here
├── README.md                 # how to run (short)
├── config.yaml
├── requirements.txt
├── .env.example              # OLLAMA_API_KEY=
├── pipeline.py               # CLI entrypoint
├── prompts/
│   ├── taxonomy.txt          # shared category definitions (also reused by eval later)
│   ├── qgen.txt
│   ├── edit_missing.txt
│   ├── edit_conflict.txt
│   ├── edit_ambiguous.txt
│   └── validate.txt
├── src/finabstain/
│   ├── __init__.py
│   ├── config.py             # load/validate config.yaml
│   ├── llm.py                # Ollama client, cache, retry, mock backend
│   ├── io_utils.py           # jsonl read/write (atomic), stage skip logic
│   ├── textnorm.py           # number/answer normalization, token counts
│   ├── diffing.py            # apply_edit(), diff verification
│   ├── stats.py              # counters, kappa, rejection reports
│   └── stages/
│       ├── s01_anonymize.py
│       ├── s02_chunk.py
│       ├── s03_assign.py
│       ├── s04_qgen.py
│       ├── s05_edit.py
│       ├── s06_checks.py
│       ├── s07_validate.py
│       ├── s08_build.py
│       └── s09_audit.py
├── scripts/
│   ├── audit_score.py        # scores the human-filled audit.csv
│   └── make_release.py       # bundles release/ folder + dataset card
├── tests/
│   ├── fixtures/mini_report.txt
│   ├── test_textnorm.py
│   ├── test_diffing.py
│   ├── test_checks.py
│   ├── test_chunk_assign.py
│   ├── test_build.py
│   └── test_pipeline_mock.py # full pipeline on mock LLM
├── data/
│   └── raw/                  # user puts report1.txt, report2.txt ... here
├── out/                      # generated; gitignored
│   ├── cache/                # LLM response cache (sha256 -> json)
│   ├── 01_anonymized/        # one .txt per report + mapping json
│   ├── 02_sections.jsonl
│   ├── 03_assigned.jsonl
│   ├── 04_qgen.jsonl
│   ├── 05_edits.jsonl
│   ├── 06_checked.jsonl
│   ├── 07_validated.jsonl
│   ├── 08_benchmark.jsonl
│   ├── 08_benchmark_short.jsonl
│   ├── audit.csv
│   ├── stats.json
│   └── run_manifest.json
└── release/                  # created by make_release.py
```

`requirements.txt`: `pyyaml`, `requests`, `tqdm`, `spacy` (+ `en_core_web_sm` install instructions in README), `scikit-learn` (cohen_kappa_score), `tiktoken` (optional, else words × 1.3), `pytest`.
Python 3.10+, type hints, dataclasses or pydantic for records.

---

## 4. config.yaml (defaults)

```yaml
seed: 42
data:
  raw_dir: data/raw
  out_dir: out
sections:
  min_words: 200
  max_words: 600            # target 300-500; split/merge paragraphs to fit
  min_numbers: 3            # eligible item sections must contain >= 3 numbers
candidates_per_category: 40 # 160 candidate items; keep 25/category after filtering
final_per_category: 25
padding:
  target_tokens: [8000]     # list: one benchmark file per length if >1
  position: random          # seeded; record position
anonymize:
  scale_factor_range: [0.55, 1.8]   # excluded band 0.9-1.1 (must not be ~1)
  fake_company_name: "Aldervane Holdings"
llm:
  backend: ollama           # ollama | mock
  base_url: https://ollama.com
  workers: 2                # keep low on free tier
  max_retries: 3
  backoff_seconds: [2, 4, 8, 16, 32, 60]
  models:
    generator: {name: "gemma4:31b", think: null, num_predict: 1024}
    validator_a: {name: "gpt-oss:120b", think: "low", num_predict: 2048}
    validator_b: {name: "nemotron-3-super", think: null, num_predict: 2048}
checks:
  conflict_min_rel_diff: 0.05
  max_inserted_words: 60
  min_kept_ratio_missing: 0.70
audit:
  n_items: 20               # 5 per category
```

---

## 5. Pipeline CLI and behavior

```
python pipeline.py --config config.yaml
    [--from-stage N] [--to-stage M]   # 1..9
    [--force]                          # recompute stages in range even if outputs exist
    [--limit K]                        # process only K items per stage (debugging)
    [--smoke]                          # tiny end-to-end run, see section 11
    [--dry-run]                        # print planned LLM calls, make none
```

**Cross-cutting requirements**
- **Stage skip:** if a stage's output exists and `--force` is not given, skip it. Write outputs to a temp file and `os.replace` (atomic).
- **Per-item resume:** within a stage, records already present in the partial output (or cache) are not recomputed.
- **LLM cache:** key = sha256 of `{model, messages, format, options, think}`. Store the raw response. A rerun after a crash costs zero calls for finished work.
- **Retry/backoff:** on 429/5xx/timeouts use `backoff_seconds`. On an explicit quota/usage-limit error, or after 5 consecutive failures, **checkpoint and exit with code 75** and print: "Quota hit. Rerun the same command after the usage window resets (~5 h)."
- **Determinism:** iterate in sorted order; all randomness comes from `random.Random(seed + stage_offset)`. Never use the global RNG.
- **Logging:** log every rejected item with `item_id`, stage, reason. Aggregate into `out/stats.json`.
- **Manifest:** `run_manifest.json` records config hash, resolved model tags, library versions, git commit if any, timestamps, number of LLM calls and cache hits.
- Never print or log the API key.

---

## 6. Stage specifications

### Stage 01: anonymize (`s01_anonymize.py`)
Input: each `data/raw/*.txt` (plain text; tables are whitespace/pipe-aligned text). Output: `out/01_anonymized/<report_id>.txt` and `<report_id>.mapping.json`.

1. **Names:** spaCy NER (`en_core_web_sm`) for ORG/PERSON/GPE, plus regex for the company's own name variants (auto-detect the most frequent ORG in the first 200 lines as "the target company", plus `Inc.`, `Corp.`, `Ltd.`, ticker in parentheses, "we/our" is left untouched). Replace target company with `fake_company_name`; other ORGs → `Company A/B/...`; PERSON → role if a role is adjacent, else `Person A/B/...`. Use one consistent mapping per report. Remove URLs, emails, phone numbers, street addresses.
2. **Numbers:** pick one factor per report from `scale_factor_range` (seeded, never within 0.9-1.1). Multiply **monetary amounts and share counts** by it. **Do not scale**: percentages, years, dates, note/section numbers, ratios like `1.5x`, page numbers. Preserve formatting (thousands separators, decimals, parentheses for negatives, `$`, unit words such as "million"). Round to the same number of decimals as the original.
3. Save the mapping and factor so the process is auditable. Residual check: after replacement, assert no original entity string from the mapping appears in the output.

Known limitation (put in dataset card): the source is a real report, so residual structure may be recognizable.

### Stage 02: chunk (`s02_chunk.py`)
Input: anonymized reports. Output: `02_sections.jsonl`, records `{section_id, report_id, index, text, n_words, n_numbers, eligible}`.

- Split on headings/blank lines into paragraph blocks; greedily merge adjacent blocks into sections of `min_words`..`max_words` words. Never split a table row; keep a table with its caption in one section when possible.
- `eligible = True` if n_words in range and n_numbers ≥ `min_numbers` and it is not boilerplate (table of contents, legal disclaimers, signature pages, exhibit lists; detect with simple keyword heuristics).
- Sections must be non-overlapping and cover the text in order.

### Stage 03: assign (`s03_assign.py`)
Input: `02_sections.jsonl`. Output: `03_assigned.jsonl`.

1. Shuffle eligible sections with the seeded RNG. Take the first `4 × candidates_per_category` as **item sections**. Assign categories round-robin over the shuffled order (so each category gets `candidates_per_category` sections), and store `rank_in_category` (0..39).
2. **All remaining sections** (eligible or not, but ≥ 80 words) form the **filler pool** used for padding (role = `filler`).
3. **Feasibility check** (raise a clear error otherwise): filler pool words × 1.3 ≥ 1.5 × max(`padding.target_tokens`); item sections ≥ 4 × `candidates_per_category`. Error message should suggest adding more reports to `data/raw/`.
4. Category must not depend on section content.

### Stage 04: qgen (`s04_qgen.py`)
For every item section, call the generator on the **original text** (regardless of assigned category). Output `04_qgen.jsonl` adding `{question, answer, evidence_span, fact_type}`.

Reject (log reason) if: invalid JSON; `evidence_span` not an exact substring of the section; normalized `answer` not inside `evidence_span`; `question` contains the answer string; question shorter than 6 words; question has no `?`.

### Stage 05: edit (`s05_edit.py`)
Apply **only the assigned category's** edit. Output `05_edits.jsonl` adding `{edited_text, question_final, edit}`.

- `answerable`: no LLM call. `edited_text = text`, `question_final = question`.
- `missing`: LLM returns `{"deletions": ["<verbatim span>", ...]}`.
- `conflict`: LLM returns `{"anchor": "<verbatim span>", "inserted_text": "...", "conflicting_value": "..."}`.
- `ambiguous`: LLM returns `{"anchor": "...", "inserted_text": "...", "distractor_value": "...", "blurred_dimension": "period|segment|unit|entity", "new_question": "...", "removed_from_question": ["word", ...]}`.

Applying edits (`diffing.py`, pure code, unit-tested):
- Every `span`/`anchor` must occur **exactly once** in the text, else the edit is invalid.
- Deletion: remove the span; clean up double spaces/empty lines.
- Insertion: insert `inserted_text` on a **new line directly after the line containing the anchor**.
- If the LLM output fails validation, retry up to 2 times, passing back the concrete error ("anchor not found", "answer still present at ...") in the prompt. After that, apply the **deterministic fallback** for `missing` only (delete every sentence containing the answer, reject if < `min_kept_ratio_missing` of words remain). For conflict/ambiguous, drop the item.
- Store `edit` = the exact structure applied, for auditing.

### Stage 06: checks (`s06_checks.py`), deterministic, no LLM
Output `06_checked.jsonl` (`passed: bool`, `fail_reasons: [...]`). Failed items stay in the file but are excluded downstream.

Common: schema valid; only the intended lines changed (verify with `difflib`: for insert, exactly one added block located right after the anchor's line and nothing else changed; for delete, only removals at the given spans); anonymization residue check passes; question doesn't contain the answer.

Per category:
- **answerable:** `edited_text == text`; normalized answer occurs in text.
- **missing:** normalized answer string **and** its numeric value (via `textnorm.numbers_in`) are absent from `edited_text`; kept-word ratio ≥ `min_kept_ratio_missing`; edit is deletions only.
- **conflict:** original answer present; `conflicting_value` present inside `inserted_text`; values differ (numbers: relative diff ≥ `conflict_min_rel_diff`; non-numbers: normalized strings differ); inserted ≤ `max_inserted_words`; `inserted_text` contains **none** of the reconcile words: `restated, revised, revision, corrected, correction, adjusted, previously, updated, amended, formerly, initially, originally, supersede`.
- **ambiguous:** original answer present; `distractor_value` present in `inserted_text` and differs from the answer (same numeric rule); reconcile words absent; every `removed_from_question` word appears in the original question and not in `new_question`; `new_question` introduces no new content words beyond the original question's; `new_question` doesn't contain the answer or distractor value.

### Stage 07: validate (`s07_validate.py`)
For every item with `passed == True`, call **validator A and validator B** on `(edited_text, question_final)` with the blind `validate.txt` prompt (short section only, never the padded context). Each returns `{"label": "answerable|missing|conflict|ambiguous", "answer": "...", "rationale": "<= 30 words"}`.

- Keep an item only if **both** labels equal the gold category. Record both labels.
- Also compute (over all checked items, before filtering): per-validator accuracy vs gold, per-category confusion matrix, **Cohen's kappa** between validators, agreement rate. Put in `stats.json`.
- Mark each kept item `needs_llm_validation`: `True` for ambiguous (labels not deterministic), `False` for the others. Used later to report a deterministic-only subset.

### Stage 08: build (`s08_build.py`)
1. For each category, order passing+validated items by `rank_in_category` and take the first `final_per_category` (25). If any category has fewer than 25, write a warning with the shortfall and the exact command to add reports/raise `candidates_per_category`, but still emit what exists.
2. **Padding:** for each `target_tokens` length, build `context` = shuffled filler sections (seeded per item) + the item's `edited_text` inserted at a random position (record `target_position` as a fraction 0-1). Join sections with `\n\n[Section k]\n` style separators (same separator style for all items). Token count via tiktoken or words × 1.3; record `approx_tokens`.
3. **Leakage guard:** exclude any filler section that contains, after normalization, the original answer, the `conflicting_value` or `distractor_value` (skip this rule when the value is shorter than 3 characters and flag `short_value_flag: true` for the human audit instead). If the pool becomes too small, reduce padding and record actual length.
4. Write `08_benchmark.jsonl` (padded) and `08_benchmark_short.jsonl` (section only, no padding; free ablation).
5. Item ids: `fab-{report_id}-{section_index}-{category[:3]}`. Sort output by id for stable diffs.

### Stage 09: audit (`s09_audit.py`)
Write `out/audit.csv` with `n_items` random items (stratified, `n/4` per category, seeded): columns `id, category(gold), question, edited_text, edit_summary, short_value_flag, human_label (blank), human_notes (blank)`. Also write `scripts/audit_score.py` which reads the filled CSV and prints label accuracy, per-category accuracy and the list of disagreements.

---

## 8. Output Schema (`08_benchmark.jsonl` and `08_benchmark_short.jsonl`)

Each line in the benchmark file contains:
- `id`: string, format `fab-{report_id}-{section_index}-{cat[:3]}`
- `category`: string, "answerable" | "missing" | "conflict" | "ambiguous"
- `gold_decision`: string, "answer" | "abstain"
- `gold_reason`: string, "none" | "missing" | "conflict" | "ambiguous"
- `question`: string, the final question text
- `context`: string, the full padded context (in `08_benchmark.jsonl`) or section text (in `08_benchmark_short.jsonl`)
- `gold_answer`: string or null, the answer value if answerable, else null
- `original_answer`: string, the original answer found during qgen
- `evidence_span`: string, the verbatim span from the source section
- `fact_type`: string, fact type category
- `report_id`: string, identifier of the source financial report
- `section_id`: string, identifier of the source section
- `target_position`: float (0.0 to 1.0), relative location where item was placed in padded context
- `target_section_index`: int, 0-indexed index of item section among padding sections
- `approx_tokens`: int, estimated or tiktoken token count of context
- `edit`: object, exact edit applied (empty dict for answerable)
- `short_value_flag`: bool, whether answer/distractor is under 3 characters
- `needs_llm_validation`: bool, true for ambiguous, false for deterministic categories
- `validator_a`: object, {name, label, answer, rationale}
- `validator_b`: object, {name, label, answer, rationale}

---

## 9. Scripts and Utilities

- `scripts/audit_score.py`: reads a filled `out/audit.csv`, computes accuracy vs gold labels, per-category breakdown, prints disagreements.
- `scripts/make_release.py`: validates benchmark files, packages into `release/` directory with a generated `DATASET_CARD.md`.

---

## 10. Testing

Comprehensive unit and integration test suite:
- `tests/test_textnorm.py`: number normalization, extraction, text similarity
- `tests/test_diffing.py`: span deletion, anchor insertion, single occurrence verification
- `tests/test_checks.py`: stage 06 rule checking for all 4 categories
- `tests/test_chunk_assign.py`: chunking heuristics, non-overlapping coverage, assignment shuffle
- `tests/test_build.py`: leakage guard, padding construction, schema conformance
- `tests/test_pipeline_mock.py`: end-to-end dry run and execution using MockLLM

---

## 11. Smoke Test (`--smoke`)

`python pipeline.py --config config.yaml --smoke`
Runs a fast end-to-end verification of the pipeline:
1. Validates model connectivity and JSON format support on Ollama Cloud (or local fallback).
2. Takes 1 candidate per category (4 items total).
3. Executes stages 1-9 to verify all pipes, prompts, regexes, and serialization without running the full dataset.
