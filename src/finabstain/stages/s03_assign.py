from __future__ import annotations
import random
from pathlib import Path
from typing import List, Dict, Any

from ..config import AppConfig
from ..io_utils import read_jsonl, write_jsonl_atomic

CATEGORIES = ["answerable", "missing", "conflict", "ambiguous"]

def run_stage(config: AppConfig, force: bool = False) -> Path:
    out_file = Path(config.data.out_dir) / "03_assigned.jsonl"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return out_file

    in_file = Path(config.data.out_dir) / "02_sections.jsonl"
    sections = read_jsonl(in_file)
    if not sections:
        raise RuntimeError("No sections found in 02_sections.jsonl")

    # Sort sections by section_id for stable determinism
    sections = sorted(sections, key=lambda s: s["section_id"])

    eligible_sections = [s for s in sections if s.get("eligible")]
    ineligible_sections = [s for s in sections if not s.get("eligible")]

    rng = random.Random(config.seed + 3)
    rng.shuffle(eligible_sections)

    target_items = 4 * config.candidates_per_category

    # Feasibility check on item sections
    if len(eligible_sections) < target_items:
        raise RuntimeError(
            f"Feasibility check failed: found {len(eligible_sections)} eligible sections, "
            f"but need at least {target_items} (4 * candidates_per_category={config.candidates_per_category}). "
            f"Please add more reports to {config.data.raw_dir}/ or reduce candidates_per_category."
        )

    item_sections = eligible_sections[:target_items]
    remaining_eligible = eligible_sections[target_items:]

    # Filler pool from remaining sections with >= 80 words
    all_filler_candidates = remaining_eligible + ineligible_sections
    filler_pool = [s for s in all_filler_candidates if s.get("n_words", 0) >= 80]

    # Feasibility check on filler pool
    max_target_tokens = max(config.padding.target_tokens) if config.padding.target_tokens else 8000
    filler_words = sum(s.get("n_words", 0) for s in filler_pool)
    approx_filler_tokens = filler_words * 1.3
    required_filler_tokens = 1.5 * max_target_tokens

    if approx_filler_tokens < required_filler_tokens:
        raise RuntimeError(
            f"Feasibility check failed: filler pool has {filler_words} words (~{int(approx_filler_tokens)} tokens), "
            f"which is less than 1.5 * max target tokens ({int(required_filler_tokens)}). "
            f"Please add more reports to {config.data.raw_dir}/."
        )

    assigned_records: List[Dict[str, Any]] = []

    # Assign item sections round-robin
    for idx, item in enumerate(item_sections):
        cat = CATEGORIES[idx % len(CATEGORIES)]
        rank = idx // len(CATEGORIES)
        rec = dict(item)
        rec["role"] = "item"
        rec["category"] = cat
        rec["rank_in_category"] = rank
        assigned_records.append(rec)

    # Assign filler pool
    for filler in filler_pool:
        rec = dict(filler)
        rec["role"] = "filler"
        rec["category"] = None
        rec["rank_in_category"] = None
        assigned_records.append(rec)

    write_jsonl_atomic(out_file, assigned_records)
    return out_file
