# `src/finabstain/stages/s01_anonymize.py`

## Overview
[`src/finabstain/stages/s01_anonymize.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s01_anonymize.py) implements Stage 1 of the FinAbstain pipeline: **Entity Anonymization and Numeric Value Rescaling**. It strips personally identifiable information (PII), detects and replaces real corporate and executive names using spaCy Named Entity Recognition (NER), and applies a uniform pseudo-random scale factor to all monetary amounts and share counts. This prevents evaluated LLMs from relying on pre-training parametric memory.

---

## How It Works

1. **PII Removal**: Uses regular expressions to redact URLs, email addresses, phone numbers, and street addresses with generic tokens (`[URL]`, `[EMAIL]`, `[PHONE]`, `[ADDRESS]`).
2. **Primary Company Identification**: Analyzes the first 200 lines of the 10-K filing with spaCy NER to identify the primary reporting entity (excluding regulators like SEC, FASB, IRS).
3. **Secondary Entity Replacement**: Scans the filing for other `ORG` and `PERSON` entities, mapping them to systematic pseudonyms (e.g., `Company A`, `Person B`).
4. **Number Rescaling**: Draws a random scale factor $s \in [0.55, 1.8]$ (excluding the trivial range $0.9 \le s \le 1.1$). Scales monetary values (`$X million/billion`) and share counts, retaining original decimal precision and parenthesis conventions.
5. **Length-Ordered Substitution**: Replaces original entity names in descending order of string length to prevent partial substring collision.
6. **Metadata Persistence**: Saves anonymized text to `out/01_anonymized/{report_id}.txt` and the replacement dictionary and scale factor to `out/01_anonymized/{report_id}.mapping.json`.

---

## Functions Reference

### `get_scale_factor(rng: random.Random, factor_range: List[float]) -> float`
- **Purpose**: Samples a scaling multiplier within `factor_range`, avoiding factors close to 1.0 ($0.90 \le s \le 1.10$).
- **Parameters**:
  - `rng` (`random.Random`): Seeded random instance.
  - `factor_range` (`List[float]`): Min and max bounds `[min_f, max_f]`.
- **Returns**: `float`: Rounded 4-decimal multiplier (defaults to `1.35` if 100 draws fail).

### `remove_pii(text: str) -> str`
- **Purpose**: Replaces URLs, emails, phone numbers, and physical street addresses with anonymized placeholders.
- **Parameters**: `text` (`str`): Input raw text.
- **Returns**: `str`: Cleaned text.

### `scale_number_match(match: re.Match, factor: float) -> str`
- **Purpose**: Regex callback function that parses captured numeric strings, multiplies by `factor`, formats commas and decimals, and reattaches currency symbols and suffixes.
- **Parameters**:
  - `match` (`re.Match`): Regex match object with groups for prefix, number, and suffix.
  - `factor` (`float`): Scaling multiplier.
- **Returns**: `str`: Formatted scaled number string.

### `scale_amounts_and_shares(text: str, factor: float) -> str`
- **Purpose**: Applies regex transformations across the passage for dollar amounts and share volumes.
- **Parameters**:
  - `text` (`str`): Document text.
  - `factor` (`float`): Multiplier.
- **Returns**: `str`: Text with scaled numeric values.

### `anonymize_report(text: str, nlp: Any, config: AppConfig, report_id: str, seed: int) -> Tuple[str, Dict[str, Any]]`
- **Purpose**: Orchestrates the complete anonymization pipeline on a single filing text.
- **Parameters**:
  - `text` (`str`): Raw document content.
  - `nlp` (`Any`): Loaded spaCy language model.
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Application config.
  - `report_id` (`str`): Identifier for the report.
  - `seed` (`int`): Random seed for reproducibility.
- **Returns**: `Tuple[str, Dict[str, Any]]`: `(anonymized_text, metadata_dict)`.

### `run_stage(config: AppConfig, force: bool = False) -> List[Path]`
- **Purpose**: Stage execution entrypoint called by `pipeline.py`.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Pipeline configuration.
  - `force` (`bool`): If `True`, re-anonymizes existing outputs.
- **Returns**: `List[Path]`: List of generated `.txt` file paths in `out/01_anonymized/`.

---

## Usage Example

```python
from src.finabstain.config import AppConfig
from src.finabstain.stages.s01_anonymize import run_stage

cfg = AppConfig.load("config.yaml")
anon_files = run_stage(cfg, force=True)
print(f"Anonymized files: {anon_files}")
```
