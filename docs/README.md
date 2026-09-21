# FinAbstain Codebase Documentation

Welcome to the **FinAbstain** codebase documentation. This documentation mirrors the project structure and provides a comprehensive explanation of every Python module, class, and function across the pipeline, evaluation harness, scripts, and test suite.

---

## Project Overview

**FinAbstain** is a long-context financial reading comprehension and abstention benchmark generator. It evaluates whether Large Language Models (LLMs) can reliably abstain from answering financial queries when information is unanswerable, and accurately identify the precise rationale behind abstention across four standardized categories:

1. **`answerable`**: The passage contains exactly one unambiguous answer to the query.
2. **`missing`**: The passage is on-topic, but the specific fact requested was omitted.
3. **`conflict`**: The passage contains contradictory values for the exact same metric, period, and entity without reconciliation.
4. **`ambiguous`**: The question is underspecified along a critical dimension (period, segment, unit), making multiple distinct values equally plausible.

---

## Documentation Navigation

### Root Pipeline
- [pipeline.py](pipeline.md) (`docs/pipeline.md`): Central command-line entrypoint executing stages 1 through 9.

### Core Framework (`src/finabstain/`)
- [__init__.py](src/finabstain/__init__.md): Package root and version definition.
- [config.py](src/finabstain/config.md): Strongly-typed dataclass configuration models loaded from `config.yaml`.
- [diffing.py](src/finabstain/diffing.md): Deterministic text diff engine for atomic span deletions and insertions.
- [io_utils.py](src/finabstain/io_utils.md): Thread-safe, atomic JSONL serialization and file I/O helpers.
- [llm.py](src/finabstain/llm.md): Multi-backend LLM client (Ollama & Mock) with SHA-256 disk caching and exponential backoff.
- [stats.py](src/finabstain/stats.md): Rejection, pass rate, and inter-annotator agreement tracking (Cohen's kappa).
- [textnorm.py](src/finabstain/textnorm.md): Financial tokenization, string/number normalization, and reconciliation keyword detection.

### Pipeline Stages (`src/finabstain/stages/`)
- [s01_anonymize.py](src/finabstain/stages/s01_anonymize.md): Entity anonymization via spaCy NER and numeric value rescaling.
- [s02_chunk.py](src/finabstain/stages/s02_chunk.md): Document chunking, boilerplate removal, and section candidate filtering.
- [s03_assign.py](src/finabstain/stages/s03_assign.md): Feasibility checks, balanced round-robin category assignment, and filler pool curation.
- [s04_qgen.py](src/finabstain/stages/s04_qgen.md): Grounded financial question-answer generation via LLM.
- [s05_edit.py](src/finabstain/stages/s05_edit.md): Multi-turn constrained synthetic edit application (missing, conflict, ambiguous).
- [s06_checks.py](src/finabstain/stages/s06_checks.md): Deterministic validation rules (diff verification, leakage, entity residue, bounds).
- [s07_validate.py](src/finabstain/stages/s07_validate.md): Dual-model independent blind validation and consensus gating.
- [s08_build.py](src/finabstain/stages/s08_build.md): Benchmark assembly with needle-in-haystack 8,000-token padded contexts and isolated short contexts.
- [s09_audit.py](src/finabstain/stages/s09_audit.md): Human audit sample extraction and CSV formatting.

### Evaluation Suite (`eval/`)
- [run_eval.py](eval/run_eval.md): High-performance evaluation runner testing LLMs against benchmark items via OpenAI-compatible endpoints.
- [score.py](eval/score.md): Benchmark scoring engine calculating Macro-F1, Decision Accuracy, Over-refusal, Over-answer, EM, Token-F1, and 95% bootstrap confidence intervals.

### Utility Scripts (`scripts/`)
- [audit_score.py](scripts/audit_score.md): Validates human-annotated CSV audit files against gold labels.
- [html_to_txt.py](scripts/html_to_txt.md): SEC 10-K HTML cleaner converting tables into pipe-delimited text and stripping iXBRL tags.
- [make_release.py](scripts/make_release.md): Packages benchmark outputs, datasets, and DATASET_CARD.md for release.
- [run_all_separate.py](scripts/run_all_separate.md): Orchestrates multi-company pipeline runs across AMZN, CAT, PFE, and KO filings.

### Test Suite (`tests/`)
- [test_build.py](tests/test_build.md): Tests for padded context construction and filler leakage detection.
- [test_checks.py](tests/test_checks.md): Unit tests for deterministic validation rules across all four categories.
- [test_chunk_assign.py](tests/test_chunk_assign.md): Tests for document block splitting, merging, and boilerplate detection.
- [test_diffing.py](tests/test_diffing.md): Tests for verbatim span deletion, single-line insertion, and fallback logic.
- [test_eval_harness.py](tests/test_eval_harness.md): Tests for schema validation, thinking tag stripping, numeric equivalence, and scoring metrics.
- [test_pipeline_mock.py](tests/test_pipeline_mock.md): End-to-end multi-stage pipeline integration test running against mock LLM backend.
- [test_textnorm.py](tests/test_textnorm.md): Tests for token counting, text normalization, number parsing, and reconciliation keywords.
