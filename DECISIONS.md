# DECISIONS.md: FinAbstain Architectural Decisions and Log

## 1. Environment & Runtime
- **Python Version**: Python 3.13.7 in `.venv/`.
- **Core Dependencies**: `pyyaml`, `requests`, `tqdm`, `spacy` (with `en_core_web_sm`), `scikit-learn`, `tiktoken`, `pytest`, `beautifulsoup4`, `lxml`.
- **HTML to TXT Processing**: SEC 10-K filings often contain inline XBRL (iXBRL) tags like `<ix:header>` and `<ix:hidden>`, and split numbers across cells (e.g. `$` in one cell, amount in another). `scripts/html_to_txt.py` strips iXBRL/hidden elements, merges split currency symbols/parentheses, and emits clean pipe-delimited text for tables.

## 2. Ollama Cloud & Local Daemon Connectivity
- **Base URL & Authentication**: If `OLLAMA_API_KEY` is provided, requests are sent to `https://ollama.com` with `Authorization: Bearer <API_KEY>`. If `OLLAMA_API_BASE` is set or if no API key is present and a local Ollama daemon is running at `http://127.0.0.1:11434`, requests use the local daemon.
- **Model Tag Resolution**: The local Ollama daemon tags cloud models with `:cloud` (e.g. `gemma4:31b-cloud`), storing `remote_model: gemma4:31b`. The tag resolver matches both the configured API name and its `:cloud` variant to ensure seamless execution in both environments.
- **JSON Structured Output & Fallback**: Calls include `format: "json"`. If a model returns extra conversational text or thinking blocks, the parser extracts the outermost balanced JSON object `{...}` with up to 3 retries.
- **Thinking Parameter**: Models supporting reasoning (such as `gpt-oss:120b` with `think: "low"`) pass the parameter when configured and omit it when null.

## 3. Token Counting
- Uses `tiktoken` (using `cl100k_base`) when available; falls back to `words * 1.3`.

## 4. Anonymization & Scaling
- **Entity Replacement**: Auto-detects the primary reporting entity from the first 200 lines. Maps to `fake_company_name`. Maps secondary entities to `Company A`, `Person A`, etc.
- **Number Scaling**: Selects a seeded random factor from `scale_factor_range` (excluding [0.9, 1.1]). Only scales currency amounts (`$` prefix or "dollars/million/billion") and share counts. Excludes dates, years, percentages, note references, and ratios.

## 5. Diffing & Edit Engine
- Pure deterministic Python implementation in `src/finabstain/diffing.py`.
- Enforces strict single-occurrence for all verbatim spans and anchors.
- Deletions clean up whitespace and empty lines.
- Insertions place the new line directly below the line containing the anchor.
- Missing category has a deterministic fallback to delete sentences mentioning the answer if LLM span matching fails after retries.

## 6. Output Schema & Benchmarking
- Produces both `08_benchmark.jsonl` (padded to target token lengths) and `08_benchmark_short.jsonl` (unpadded excerpt ablation).
- All items include gold decisions, gold reasons, evidence spans, validator audits, and reproducibility metadata.
