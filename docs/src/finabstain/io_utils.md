# `src/finabstain/io_utils.py`

## Overview
[`src/finabstain/io_utils.py`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/io_utils.py) provides safe, atomic file I/O operations tailored for pipeline execution and resume workflows. It implements atomic JSONL writing via temporary files, incremental appending, skip detection, and completed ID extraction.

---

## How It Works

- **Atomic Writing**: When writing dataset outputs, `write_jsonl_atomic` first writes records to a hidden temporary file in the target directory (`.{stem}_*.tmp`) before performing an atomic `os.replace`. This prevents file corruption if the process is killed midway.
- **Fault-Tolerant Reading**: Reads line-by-line JSONL streams, ignoring empty lines or truncated lines.
- **Stage Skipping & Resuming**: Facilitates resumption of long runs by inspecting whether intermediate stage files exist and gathering IDs of items that have already been processed.

---

## Functions Reference

### `read_jsonl(path: str | Path) -> List[Dict[str, Any]]`
- **Purpose**: Reads a JSON Lines file into a list of Python dictionaries.
- **Parameters**:
  - `path` (`str | Path`): Filepath to read.
- **Returns**: `List[Dict[str, Any]]`: List of parsed records. If file does not exist, safely returns an empty list `[]`.

### `write_jsonl_atomic(path: str | Path, records: Iterable[Dict[str, Any]]) -> None`
- **Purpose**: Atomically writes an iterable of dictionaries to a JSONL file.
- **Parameters**:
  - `path` (`str | Path`): Target destination file path.
  - `records` (`Iterable[Dict[str, Any]]`): Sequence of record dictionaries.
- **Behavior**: Creates parent directories if missing, writes to a temp file, and swaps it atomically via `os.replace`. If an exception occurs, cleans up the temp file.

### `append_jsonl_record(path: str | Path, record: Dict[str, Any]) -> None`
- **Purpose**: Appends a single JSON dictionary record to a JSONL file with UTF-8 encoding.
- **Parameters**:
  - `path` (`str | Path`): Destination JSONL file path.
  - `record` (`Dict[str, Any]`): Single record dictionary.

### `get_completed_item_ids(path: str | Path, id_key: str = "id") -> set`
- **Purpose**: Collects unique item or section identifiers from an existing JSONL output.
- **Parameters**:
  - `path` (`str | Path`): JSONL file path.
  - `id_key` (`str`): Primary key attribute to look for (default: `"id"`, falls back to `"section_id"`).
- **Returns**: `set`: Set of completed string IDs.

### `should_skip_stage(output_file: str | Path, force: bool = False) -> bool`
- **Purpose**: Determines whether a pipeline stage can be skipped.
- **Parameters**:
  - `output_file` (`str | Path`): Expected stage output file path.
  - `force` (`bool`): If `True`, always returns `False` to force recomputation.
- **Returns**: `bool`: `True` if `output_file` exists and its file size is greater than 0 bytes.

---

## Usage Example

```python
from src.finabstain.io_utils import write_jsonl_atomic, read_jsonl

records = [{"id": 1, "status": "ok"}, {"id": 2, "status": "ok"}]
write_jsonl_atomic("out/sample.jsonl", records)

loaded = read_jsonl("out/sample.jsonl")
assert len(loaded) == 2
```
