# Evaluation Harness Design Decisions (FinAbstain)

This document records key technical decisions made while designing and implementing the FinAbstain evaluation and scoring harness in `./eval/`.

---

### 1. Dataset Schema Compatibility (`source_report` vs. `report_id`)
- **Context**: The evaluation specification dictates confirming that `source_report` exists on line 1 of the dataset, while `release/benchmark.jsonl` stores the filing identifier under `report_id`. The specification also states: *"Never modify the dataset. Compute and log its SHA-256."*
- **Decision**: The evaluation runner verifies that either `source_report` or `report_id` exists on line 1. In memory, it normalizes `report_id` into `source_report` for all downstream scoring and company-level breakdowns (`amzn`, `cat`, `pfe`, `ko`), leaving the release dataset byte-for-byte untouched.

---

### 2. Thinking Control for Qwen3.5 & Strip Logic
- **Context**: Qwen3.5 models may emit `<think>...</think>` blocks which can corrupt raw JSON extraction.
- **Decision**:
  - Request level: Every HTTP POST to `/v1/chat/completions` includes `"chat_template_kwargs": {"enable_thinking": false}`.
  - Server level: The PBS script launches `llama-server` with `--chat-template-kwargs '{"enable_thinking":false}'`.
  - Harness level: `run_eval.py` detects any occurrence of `<think>` in the response, sets `think_stripped=True`, and strips the `<think>...</think>` content before JSON extraction. Both `think_stripped` and `raw_text` are recorded in `raw.jsonl`.

---

### 3. Balanced JSON Extraction & Consistency Rules
- **Context**: Frontier models without grammar or JSON schema constraints may include conversational filler or markdown formatting around the JSON object.
- **Decision**: `extract_first_balanced_json` parses the first balanced `{...}` using brace depth counting that respects quoted strings and escape characters.
- **Consistency Enforcement**:
  - If `decision == "answer"`: `reason` must strictly equal `"none"`.
  - If `decision == "abstain"`: `reason` must strictly be one of `{"missing", "conflict", "ambiguous"}`.
  Any violation, missing key, unparsable string, or network/context error is designated `PARSE_FAIL`.

---

### 4. Handling `PARSE_FAIL` in Metrics
- **Context**: How to treat malformed or unparsable outputs in multi-class metrics.
- **Decision**: A `PARSE_FAIL` prediction is treated as wrong on every metric. In confusion matrices, it occupies its own explicit column (`pred_PARSE_FAIL`). In macro-F1, it acts as a false negative for whichever gold class was present, properly penalizing models that fail to follow format.

---

### 5. Pure NumPy Implementation of Macro-F1 (No scikit-learn)
- **Context**: Compute nodes in high-performance computing (HPC) clusters frequently run in offline air-gapped environments without external Python package indexes.
- **Decision**: Implemented multi-class precision, recall, and unweighted macro-F1 directly using standard Python and NumPy. Classes with zero support in any slice or resample are safely excluded from the macro average.

---

### 6. Answer Normalization & Financial Numeric Parsing
- **Context**: Financial answers can be expressed in varying notations (e.g. `"$1.2 million"`, `"1,200,000"`, `"1.2M"`, `"(340)"`, `"12.5 %"`).
- **Decision**:
  - String normalization lowercases, removes currency symbols, strips commas and trailing periods, and normalizes parenthesized negatives `(340) -> -340`.
  - `parse_numeric_val` extracts magnitude multipliers (`million`/`m` $\to 10^6$, `billion`/`b` $\to 10^9$, `thousand`/`k` $\to 10^3$).
  - Answer Exact Match (EM) evaluates to `1.0` if normalized strings match, or if the normalized gold answer is a substring of the model prediction, or if their parsed numeric values match within a $10^{-4}$ tolerance.

---

### 7. Port Allocation in PBS
- **Context**: Concurrent cluster jobs sharing the same physical or virtual node could collide if bound to a hardcoded port.
- **Decision**: The PBS job script extracts the numeric portion of `$PBS_JOBID` and binds the server to port `8000 + (JOB_NUM % 1000)`.
