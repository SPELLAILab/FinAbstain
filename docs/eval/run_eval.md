# `eval/run_eval.py`

## Overview
[`eval/run_eval.py`](file:///Users/kartiksirohi/FinAbstain/eval/run_eval.py) is the evaluation runner for FinAbstain. It evaluates local or remote LLMs served via OpenAI-compatible endpoints (such as `llama-server`) against the benchmark dataset. It features strict dataset schema validation, sequential request execution, network retry handling, resume support, context overflow checks, `<think>` block stripping, and experiment manifest logging.

---

## How It Works

1. **Dataset Schema Verification**: Calculates the SHA-256 hash of the benchmark file and validates that all mandatory fields (`id`, `category`, `gold_decision`, `gold_reason`, `question`, `gold_answer`, `context`, `needs_llm_validation`, `source_report`) and allowed category enum values exist on line 1.
2. **Server Metadata Query**: Queries the `/props` or `/v1/models` endpoints on the target `llama-server` to automatically discover and log the loaded GGUF filename and server build version.
3. **Sequential Execution & Prompt Templating**:
   - For each item, formats the prompt template (`eval/prompts/eval_prompt.txt`), inserting `{context}` and `{question}`.
   - Disables model thinking (`"chat_template_kwargs": {"enable_thinking": False}`) and sets `temperature: 0` and `seed: 42`.
4. **Thinking Block Stripping**: Scans raw completions for `<think>...</think>` tags, strips reasoning tokens from the parsed output, and records whether thinking occurred via `think_stripped`.
5. **Context Overflow & Error Guarding**: Monitors token usage (`prompt_tokens + completion_tokens`) against `--ctx` (nominally 16,384). If the context window is exceeded, records an error without crashing the run.
6. **Resume Capability**: Reads existing IDs from `eval_out/{model_name}/raw.jsonl` on startup and seamlessly resumes from the next item.
7. **Manifest Logging**: Writes complete environment and execution metadata to `eval_out/{model_name}/manifest.json`.

---

## Functions Reference

### `compute_sha256(filepath: Path) -> str`
- **Purpose**: Computes SHA-256 hex digest of a file in 64KB chunks.
- **Parameters**: `filepath` (`Path`).
- **Returns**: `str`: 64-character hash.

### `validate_dataset_schema(filepath: Path) -> Tuple[List[Dict[str, Any]], str]`
- **Purpose**: Validates dataset completeness, required keys, and category enumerations.
- **Parameters**: `filepath` (`Path`): Path to benchmark JSONL file.
- **Returns**: `Tuple[List[Dict[str, Any]], str]`: `(items_list, dataset_sha256)`.
- **Raises**: `FileNotFoundError` or `ValueError` if fields are missing or values are out of bounds.

### `query_server_metadata(base_url: str) -> Tuple[Optional[str], Optional[str]]`
- **Purpose**: Queries `llama-server` for loaded model name and server version.
- **Parameters**: `base_url` (`str`): Base URL (e.g. `http://127.0.0.1:8080`).
- **Returns**: `Tuple[Optional[str], Optional[str]]`: `(gguf_model_name, server_version)`.

### `strip_thinking(raw_text: str) -> Tuple[str, bool]`
- **Purpose**: Removes `<think>...</think>` blocks from model generation.
- **Parameters**: `raw_text` (`str`): Raw completion text.
- **Returns**: `Tuple[str, bool]`: `(clean_text, think_tag_appeared)`.

### `main() -> None`
- **Purpose**: CLI entrypoint handling arguments, sequential evaluation loop, progress reporting, and manifest generation.
- **CLI Options**:
  - `--data`: Path to benchmark dataset (default: `release/benchmark.jsonl`).
  - `--model-name`: Model identifier for output paths (required).
  - `--base-url`: Server endpoint URL (default: `http://127.0.0.1:8080`).
  - `--out-dir`: Directory for outputs (default: `eval_out/<model-name>`).
  - `--limit`: Limit number of items.
  - `--smoke`: Smoke test mode (2 items per category = 8 items).
  - `--ctx`: Context window limit (default: `16384`).
  - `--max-tokens`: Max completion tokens (default: `200`).
  - `--prompt-file`: Prompt template path (default: `eval/prompts/eval_prompt.txt`).

---

## Usage Example

```bash
# Run full evaluation on a local llama-server instance
python eval/run_eval.py --model-name granite-3.2-8b --base-url http://127.0.0.1:8080

# Fast smoke test (8 items)
python eval/run_eval.py --model-name qwen-2.5-7b --smoke
```
