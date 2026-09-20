from __future__ import annotations
import csv
import random
from pathlib import Path
from typing import List, Dict, Any

from ..config import AppConfig
from ..io_utils import read_jsonl

CATEGORIES = ["answerable", "missing", "conflict", "ambiguous"]

def format_edit_summary(cat: str, edit: Dict[str, Any]) -> str:
    if cat == "answerable":
        return "None (verbatim original)"
    elif cat == "missing":
        dels = edit.get("deletions", [])
        return f"Deletions: {dels}"
    elif cat == "conflict":
        ins = edit.get("inserted_text", "")
        cval = edit.get("conflicting_value", "")
        return f"Inserted: {ins} [conflicting_value={cval}]"
    elif cat == "ambiguous":
        dim = edit.get("blurred_dimension", "")
        ins = edit.get("inserted_text", "")
        rm = edit.get("removed_from_question", [])
        return f"Dimension: {dim} | Inserted: {ins} | Removed: {rm}"
    return str(edit)

def run_stage(config: AppConfig, force: bool = False) -> Path:
    out_dir = Path(config.data.out_dir)
    audit_file = out_dir / "audit.csv"

    if not force and audit_file.exists() and audit_file.stat().st_size > 0:
        return audit_file

    in_file = out_dir / "08_benchmark_short.jsonl"
    records = read_jsonl(in_file)
    if not records:
        in_file = out_dir / "08_benchmark.jsonl"
        records = read_jsonl(in_file)

    by_cat: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CATEGORIES}
    for r in records:
        cat = r.get("category")
        if cat in by_cat:
            by_cat[cat].append(r)

    total_audit_target = config.audit.n_items
    per_cat_target = max(1, total_audit_target // len(CATEGORIES))

    rng = random.Random(config.seed + 9000)
    audit_samples: List[Dict[str, Any]] = []

    for cat in CATEGORIES:
        pool = list(by_cat[cat])
        rng.shuffle(pool)
        audit_samples.extend(pool[:per_cat_target])

    fieldnames = [
        "id",
        "category",
        "question",
        "edited_text",
        "edit_summary",
        "short_value_flag",
        "human_label",
        "human_notes",
    ]

    with open(audit_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in audit_samples:
            cat = s.get("category", "")
            writer.writerow({
                "id": s.get("id", ""),
                "category": cat,
                "question": s.get("question", ""),
                "edited_text": s.get("context", ""),
                "edit_summary": format_edit_summary(cat, s.get("edit", {})),
                "short_value_flag": s.get("short_value_flag", False),
                "human_label": "",
                "human_notes": "",
            })

    return audit_file
