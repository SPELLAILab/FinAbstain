# `src/finabstain/stages/s02_chunk.py`

## Overview
[`src/finabstain/stages/s02_chunk.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/stages/s02_chunk.py) implements Stage 2: **Document Chunking, Boilerplate Filtering, and Section Extraction**. It splits anonymized reports into cohesive text blocks (paragraphs, financial tables, notes), merges blocks into sections sized for reading comprehension ($200\text{--}600$ words), and filters out regulatory boilerplate and low-information text.

---

## How It Works

1. **Paragraph & Table Splitting**: Separates text on double newlines (`\n{2,}`). For oversized monolithic blocks ($>500$ words), it splits along sentence boundaries into balanced ~250-word sub-blocks.
2. **Greedy Section Merging**: Iterates through blocks and merges consecutive blocks until the cumulative word count satisfies the `[min_words, max_words]` configuration bounds (nominally 200–600 words).
3. **Boilerplate Detection**: Scans candidate passages against regex patterns matching common SEC filing boilerplate (e.g. Table of Contents, Exhibit Index, Signature pages, Certifications pursuant to Rule 13a-14).
4. **Eligibility Criteria**: A section is flagged as `eligible = True` if:
   - Word count falls between `min_words` and `max_words + 150`.
   - Contains at least `min_numbers` numeric values (nominally $\ge 3$).
   - Contains no boilerplate matches.
5. **Output**: Writes all sections (eligible and filler candidates) to `out/02_sections.jsonl`.

---

## Functions Reference

### `is_boilerplate(text: str) -> bool`
- **Purpose**: Checks if a text excerpt contains regulatory or navigational boilerplate patterns.
- **Parameters**: `text` (`str`): Section text.
- **Returns**: `bool`: `True` if any boilerplate regex matches.

### `split_into_blocks(text: str) -> List[str]`
- **Purpose**: Splits raw filing text into cohesive paragraphs and table blocks, sub-splitting huge blocks on sentence boundaries.
- **Parameters**: `text` (`str`): Raw report text.
- **Returns**: `List[str]`: List of distinct text blocks.

### `merge_blocks_into_sections(blocks: List[str], min_words: int, max_words: int) -> List[str]`
- **Purpose**: Merges adjacent blocks into cohesive sections within target word bounds.
- **Parameters**:
  - `blocks` (`List[str]`): List of individual blocks.
  - `min_words` (`int`): Target minimum section length.
  - `max_words` (`int`): Target maximum section length.
- **Returns**: `List[str]`: List of assembled section strings.

### `run_stage(config: AppConfig, force: bool = False) -> Path`
- **Purpose**: Stage execution entrypoint. Processes all anonymized texts and generates `out/02_sections.jsonl`.
- **Parameters**:
  - `config` ([`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118)): Pipeline configuration.
  - `force` (`bool`): If `True`, re-chunks even if output exists.
- **Returns**: `Path`: Path to `02_sections.jsonl`.

---

## JSONL Output Record Schema

Each record in `02_sections.jsonl` contains:
```json
{
  "section_id": "amzn_sec0012",
  "report_id": "amzn",
  "index": 12,
  "text": "...",
  "n_words": 342,
  "n_numbers": 8,
  "eligible": true
}
```
