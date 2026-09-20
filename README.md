# FinAbstain: Long-Context Financial Report Abstention Benchmark Builder

FinAbstain is an automated benchmark generator that builds balanced, high-quality abstention benchmarks from real SEC 10-K financial reports. It evaluates whether an LLM can recognize when a question cannot be answered unambiguously from long financial context, and accurately explain *why* according to the benchmark taxonomy:

1. **answerable**: Exactly one unambiguous answer exists in context.
2. **missing**: The context is on-topic, but the required fact is absent.
3. **conflict**: Two or more contradictory values exist for the exact same metric, period, and entity, with nothing to reconcile them.
4. **ambiguous**: The question is underspecified along a key dimension (e.g. period, segment, unit, entity), making multiple answers valid.

---

## 1. Setup & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Ollama Cloud account or local Ollama daemon

### Create Virtual Environment
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Environment Variables
Copy `.env.example` to `.env` if using Ollama Cloud with API Key:
```bash
cp .env.example .env
```
Configure your keys:
```bash
# In .env or shell environment
export OLLAMA_API_KEY="your-ollama-api-key"
# Optional: if using local Ollama daemon
export OLLAMA_API_BASE="http://127.0.0.1:11434"
```

---

## 2. Converting Financial HTML Reports

If you have SEC 10-K filings in HTML format (e.g. `data/raw/report.html`), convert them to clean text using the bundled converter:
```bash
python scripts/html_to_txt.py data/raw/report.html data/raw/report.txt
```
This converter strips iXBRL metadata and hidden tags, cleans non-breaking spaces, and aligns tables into pipe-delimited format.

---

## 3. Running the Pipeline

To run the full end-to-end dataset generation pipeline:
```bash
python pipeline.py --config config.yaml
```

### Useful CLI Options
- `--smoke`: Run a fast end-to-end smoke test (1 candidate per category, pre-flight model JSON tests)
- `--dry-run`: Display planned LLM calls and category breakdowns without invoking models
- `--force`: Recompute stages even if cached stage outputs exist
- `--from-stage N` / `--to-stage M`: Run a specific stage range (stages 1 to 9)
- `--limit K`: Process at most K items per stage (useful for testing)

---

## 4. Pipeline Stages

- **Stage 01: Anonymize (`s01_anonymize.py`)**: Replaces entity names using spaCy NER and scales monetary amounts and share counts using a seeded scale factor (outside [0.9, 1.1]).
- **Stage 02: Chunk (`s02_chunk.py`)**: Merges paragraph and table blocks into 200–600 word sections, filtering boilerplate.
- **Stage 03: Assign (`s03_assign.py`)**: Shuffles eligible sections and assigns categories round-robin; forms the filler pool for padding.
- **Stage 04: QGen (`s04_qgen.py`)**: Uses the generator model (`gemma4:31b`) to draft question-answer pairs and evidence spans from the original text.
- **Stage 05: Edit (`s05_edit.py`)**: Proposes verbatim deletions (missing) or single-line insertions (conflict/ambiguous). Code deterministically applies edits.
- **Stage 06: Checks (`s06_checks.py`)**: Deterministic diff and validation rules verifying no reconciliation words, valid relative diffs, and exact edits.
- **Stage 07: Validate (`s07_validate.py`)**: Blind cross-validation by two independent models (`gpt-oss:120b` and `nemotron-3-super`), requiring complete agreement with the gold label.
- **Stage 08: Build (`s08_build.py`)**: Constructs padded long-context benchmarks (`08_benchmark.jsonl`) with leakage guards and short unpadded ablations (`08_benchmark_short.jsonl`).
- **Stage 09: Audit (`s09_audit.py`)**: Generates stratified sample `out/audit.csv` for human verification.

---

## 5. Human Audit & Scoring

Audit items are written to `out/audit.csv`. A human auditor inspects:
1. **Gold label match**: Does the text strictly support the gold category?
2. **Question quality**: Is the question natural, grammatical, and self-contained?
3. **Leakage**: Does the padding context accidentally contain an unintended second answer or reconcile a conflict?

After filling in `human_label` in `out/audit.csv`, score the results:
```bash
python scripts/audit_score.py out/audit.csv
```

---

## 6. Packaging a Release

To create a release bundle with `DATASET_CARD.md`:
```bash
python scripts/make_release.py
```
This produces `release/benchmark.jsonl`, `release/benchmark_short.jsonl`, `release/stats.json`, and `release/DATASET_CARD.md`.

---

## 7. Running Tests

Run the full pytest suite:
```bash
pytest -v
```
