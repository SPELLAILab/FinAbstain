# `src/finabstain/llm.py`

## Overview
[`src/finabstain/llm.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/llm.py) provides the unified LLM invocation client for FinAbstain. It encapsulates:
1. Model tag discovery and verification against Ollama endpoints.
2. SHA-256 payload disk caching to ensure determinism and reduce API costs.
3. Robust error recovery, exponential backoff, and HTTP 429/quota handling.
4. Robust JSON extraction from unstructured or fenced model generations.
5. Deterministic mock generation backend for offline testing.

---

## How It Works

- **Model Tag Resolution**: On startup, `LLMClient` checks `/api/tags` and `/v1/models` on the Ollama endpoint. It maps requested model names to exact available cloud/local tags (e.g. `gemma4:31b` to `gemma4:31b-cloud` or `gemma4:31b:cloud`).
- **Disk Caching**: Every request payload (model name, prompt messages, temperature, seed, format, think settings) is hashed using SHA-256. If a matching `.json` file exists in `cache_dir`, the cached output is returned instantly without making an HTTP request.
- **Robust JSON Extraction**: Models occasionally output reasoning before JSON or wrap outputs in markdown backticks. `extract_balanced_json` uses brace depth counting to find and parse the outermost balanced `{ ... }` JSON object.
- **Rate-Limiting & Quota Management**: Retries on transient errors using an exponential backoff schedule. If 429 or quota limit errors persist, or 5 consecutive failures occur, it gracefully exits with code `75` informing the user of the usage reset window.
- **Mock Mode**: When `config.backend == "mock"`, it bypasses network requests and evaluates regexes on prompt content to return valid synthetic responses for QGen, Edit, and Validation stages.

---

## Functions and Classes Reference

### `sha256_key(data: Dict[str, Any]) -> str`
- **Purpose**: Computes a stable hex digest for any serializable dictionary using canonical JSON sorting.
- **Parameters**: `data` (`Dict[str, Any]`).
- **Returns**: `str`: 64-character SHA-256 hash.

### `extract_balanced_json(text: str) -> Optional[Dict[str, Any]]`
- **Purpose**: Extracts and parses the outermost balanced JSON object `{ ... }` from a string.
- **Parameters**: `text` (`str`): Raw LLM completion text.
- **Returns**: `Optional[Dict[str, Any]]`: Parsed dictionary, or `None` if no valid JSON structure could be identified.
- **Mechanism**: Strips markdown fences, tracks string quotes and escape characters, balances opening/closing braces, and falls back to regex matching if bracket counting encounters trailing issues.

### `class LLMClient`
The primary client interface for invoking model completions.

#### `__init__(self, config: LLMConfig, cache_dir: str | Path, seed: int = 42)`
- **Parameters**:
  - `config` ([`LLMConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L14-L22)): Configuration settings.
  - `cache_dir` (`str | Path`): Directory where SHA-256 cache files are stored.
  - `seed` (`int`): Global random seed (default: `42`).

#### `_is_local_reachable(self, url: str) -> bool`
- **Purpose**: Pings a local Ollama daemon (`http://127.0.0.1:11434/api/tags`) with a short timeout.
- **Returns**: `bool`: `True` if local endpoint responds with HTTP 200.

#### `_resolve_and_verify_models(self) -> None`
- **Purpose**: Queries the endpoint for available model tags, resolves alias tags, and verifies all required models exist.
- **Raises**: `RuntimeError` if any configured model tag cannot be located on the endpoint.

#### `_get_cache(self, key: str) -> Optional[Dict[str, Any]]`
- **Purpose**: Retrieves a cached response by SHA-256 hash key.
- **Returns**: Parsed cached dict or `None`.

#### `_save_cache(self, key: str, data: Dict[str, Any]) -> None`
- **Purpose**: Persists response payload to disk under `cache_dir/{key}.json`.

#### `call_chat(self, model_role: str, messages: List[Dict[str, str]], json_format: bool = True, stats_tracker: Optional[Any] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]`
- **Purpose**: Executes a chat completion call for a designated model role.
- **Parameters**:
  - `model_role` (`str`): Role defined in config (`"generator"`, `"validator_a"`, `"validator_b"`).
  - `messages` (`List[Dict[str, str]]`): List of message dicts `[{"role": "...", "content": "..."}]`.
  - `json_format` (`bool`): When `True`, sets `"format": "json"` in payload and parses returned JSON.
  - `stats_tracker` (`Optional[StatsTracker]`): If provided, increments LLM call and cache hit counts.
- **Returns**:
  - `Tuple[Optional[str], Optional[Dict[str, Any]], bool]`: `(raw_text, parsed_json, from_cache)`.

#### `_mock_call(self, model_role: str, messages: List[Dict[str, str]], stats_tracker: Optional[Any] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]`
- **Purpose**: Generates deterministic mock responses for testing all pipeline stages without live LLMs.

---

## Usage Example

```python
from src.finabstain.config import LLMConfig, ModelConfig
from src.finabstain.llm import LLMClient

cfg = LLMConfig(
    backend="mock",
    models={"generator": ModelConfig(name="gemma4:31b")}
)
client = LLMClient(cfg, cache_dir="out/cache")

messages = [{"role": "user", "content": "building a reading-comprehension test\nExcerpt: Net sales were $100M."}]
raw, data, from_cache = client.call_chat("generator", messages)
print(data["question"])
```
