# `src/finabstain/config.py`

## Overview
[`src/finabstain/config.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py) defines strongly-typed configuration dataclasses for FinAbstain. It handles parsing, validation, and defaulting of all parameters specified in `config.yaml`, covering LLM settings, data paths, section parsing limits, padding parameters, anonymization rules, check thresholds, and audit sizes.

---

## How It Works
The configuration is structured hierarchically using Python `@dataclass` decorators:
- Each configuration sub-domain (e.g. `data`, `sections`, `llm`, `checks`, `audit`, `padding`, `anonymize`) has a dedicated dataclass.
- [`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118) acts as the root configuration object.
- The `AppConfig.load()` method reads a YAML file via `PyYAML`, and `AppConfig.from_dict()` parses dictionary structures, populating nested configuration classes with safe defaults.

---

## Classes and Functions Reference

### `ModelConfig` (dataclass)
Represents configuration for a specific LLM model role.
- **Attributes**:
  - `name: str` - Model identifier or tag (e.g., `"gemma4:31b"`, `"gpt-oss:120b"`, `"nemotron-3-super"`).
  - `think: Optional[str]` - Thinking mode setting (e.g., `"low"`, `"none"`, or `None`).
  - `num_predict: int` - Maximum tokens to predict (default: `1024`).

### `LLMConfig` (dataclass)
Represents global LLM provider configuration.
- **Attributes**:
  - `backend: str` - Backend type (`"ollama"` or `"mock"`, default: `"ollama"`).
  - `base_url: str` - Base endpoint URL (default: `"https://ollama.com"`).
  - `workers: int` - Concurrent worker count (default: `2`).
  - `max_retries: int` - Max retries upon network or server errors (default: `3`).
  - `backoff_seconds: List[int]` - Exponential backoff ladder (default: `[2, 4, 8, 16, 32, 60]`).
  - `models: Dict[str, ModelConfig]` - Mapping of role name (`"generator"`, `"validator_a"`, `"validator_b"`) to [`ModelConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L8-L13).

### `DataConfig` (dataclass)
Defines filesystem directory paths.
- **Attributes**:
  - `raw_dir: str` - Path to raw reports (default: `"data/raw"`).
  - `out_dir: str` - Path for generated pipeline outputs (default: `"out"`).

### `SectionsConfig` (dataclass)
Defines chunking and section extraction criteria.
- **Attributes**:
  - `min_words: int` - Minimum word count for an eligible section (default: `200`).
  - `max_words: int` - Maximum target word count for section merging (default: `600`).
  - `min_numbers: int` - Minimum count of numerical tokens required for section eligibility (default: `3`).

### `PaddingConfig` (dataclass)
Defines long-context haystack padding parameters.
- **Attributes**:
  - `target_tokens: List[int]` - Target token lengths for padded contexts (default: `[8000]`).
  - `position: str` - Target insertion strategy (default: `"random"`).

### `AnonymizeConfig` (dataclass)
Defines anonymization and number scaling settings.
- **Attributes**:
  - `scale_factor_range: List[float]` - Permitted uniform range for financial figure scaling (default: `[0.55, 1.8]`).
  - `fake_company_name: str` - Target replacement name for primary company (default: `"Aldervane Holdings"`).

### `ChecksConfig` (dataclass)
Thresholds for deterministic quality checks.
- **Attributes**:
  - `conflict_min_rel_diff: float` - Minimum relative difference required between conflicting numbers (default: `0.05`, i.e., 5%).
  - `max_inserted_words: int` - Maximum word length of inserted synthetic sentences (default: `60`).
  - `min_kept_ratio_missing: float` - Minimum ratio of words that must remain after deletion in missing edits (default: `0.70`).

### `AuditConfig` (dataclass)
Settings for human audit sampling.
- **Attributes**:
  - `n_items: int` - Target number of benchmark items to sample into `audit.csv` (default: `20`).

### `AppConfig` (dataclass)
Top-level application configuration container.
- **Attributes**:
  - `seed: int` - Master random seed for reproducibility (default: `42`).
  - `data: DataConfig`
  - `sections: SectionsConfig`
  - `candidates_per_category: int` - Number of initial candidates generated per category (default: `40`).
  - `final_per_category: int` - Final target items per category after filtering (default: `25`).
  - `padding: PaddingConfig`
  - `anonymize: AnonymizeConfig`
  - `llm: LLMConfig`
  - `checks: ChecksConfig`
  - `audit: AuditConfig`
  - `raw_dict: Dict[str, Any]` - Unmodified dictionary representation of loaded YAML.
- **Methods**:
  - `load(path: str | Path) -> AppConfig`: Reads a YAML file from disk and parses it into an `AppConfig` instance.
  - `from_dict(data: Dict[str, Any]) -> AppConfig`: Instantiates an `AppConfig` from a dictionary, hydrating sub-dataclasses.

---

## Usage Example

```python
from src.finabstain.config import AppConfig

# Load from YAML
cfg = AppConfig.load("config.yaml")

print(f"Seed: {cfg.seed}")
print(f"Generator model: {cfg.llm.models['generator'].name}")
print(f"Target tokens: {cfg.padding.target_tokens}")
```
