from __future__ import annotations
import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Generator, Iterable, Optional

def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    records = []
    with open(p, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                # Corrupted line or truncated line
                continue
    return records

def write_jsonl_atomic(path: str | Path, records: Iterable[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=p.parent, prefix=f".{p.stem}_", suffix=".tmp")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(temp_path, p)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

def append_jsonl_record(path: str | Path, record: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def get_completed_item_ids(path: str | Path, id_key: str = "id") -> set:
    p = Path(path)
    if not p.exists():
        return set()
    ids = set()
    for item in read_jsonl(p):
        if id_key in item:
            ids.add(item[id_key])
        elif "section_id" in item:
            ids.add(item["section_id"])
    return ids

def should_skip_stage(output_file: str | Path, force: bool = False) -> bool:
    if force:
        return False
    p = Path(output_file)
    return p.exists() and p.stat().st_size > 0
