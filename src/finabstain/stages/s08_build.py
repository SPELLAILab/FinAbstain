from __future__ import annotations
import random
from pathlib import Path
from typing import List, Dict, Any

from ..config import AppConfig
from ..io_utils import read_jsonl, write_jsonl_atomic
from ..textnorm import count_tokens, answer_in_text

CATEGORIES = ["answerable", "missing", "conflict", "ambiguous"]

def construct_padded_context(
    item_text: str,
    fillers: List[Dict[str, Any]],
    target_tokens: int,
    rng: random.Random
) -> tuple[str, float, int, int]:
    shuffled_fillers = list(fillers)
    rng.shuffle(shuffled_fillers)

    item_tokens = count_tokens(item_text)
    chosen_fillers: List[str] = []
    current_tokens = item_tokens

    for f in shuffled_fillers:
        f_toks = count_tokens(f["text"])
        if current_tokens + f_toks > target_tokens and current_tokens >= (target_tokens * 0.85):
            break
        chosen_fillers.append(f["text"])
        current_tokens += f_toks

    # Insert item at random position
    n_sections = len(chosen_fillers) + 1
    target_idx = rng.randint(0, len(chosen_fillers))
    target_position = target_idx / max(n_sections - 1, 1)

    all_sections = chosen_fillers[:target_idx] + [item_text] + chosen_fillers[target_idx:]

    context_parts = []
    for idx, sec in enumerate(all_sections, start=1):
        context_parts.append(f"[Section {idx}]\n{sec}")

    context_str = "\n\n".join(context_parts)
    actual_tokens = count_tokens(context_str)

    return context_str, target_position, target_idx, actual_tokens

def run_stage(config: AppConfig, force: bool = False) -> List[Path]:
    out_dir = Path(config.data.out_dir)
    bench_file = out_dir / "08_benchmark.jsonl"
    short_file = out_dir / "08_benchmark_short.jsonl"

    if not force and bench_file.exists() and bench_file.stat().st_size > 0:
        return [bench_file, short_file]

    in_file = out_dir / "07_validated.jsonl"
    validated_records = read_jsonl(in_file)
    valid_items = [r for r in validated_records if r.get("validated")]

    # Group by category and take top final_per_category
    by_category: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CATEGORIES}
    for item in valid_items:
        cat = item.get("category")
        if cat in by_category:
            by_category[cat].append(item)

    selected_items: List[Dict[str, Any]] = []
    for cat in CATEGORIES:
        items = sorted(by_category[cat], key=lambda x: x.get("rank_in_category", 0))
        target_n = config.final_per_category
        shortfall = target_n - len(items)
        if shortfall > 0:
            print(
                f"[WARNING] Category '{cat}' has {len(items)} items, target is {target_n} (shortfall: {shortfall}).\n"
                f"To obtain the full target, add more financial reports to '{config.data.raw_dir}/' or raise candidates_per_category."
            )
        selected_items.extend(items[:target_n])

    # Load filler pool
    assigned_file = out_dir / "03_assigned.jsonl"
    assigned = read_jsonl(assigned_file)
    filler_pool = [s for s in assigned if s.get("role") == "filler"]

    # If filler pool is empty (e.g. small debug or single short report), fallback to unused item sections
    if not filler_pool:
        selected_ids = {item["section_id"] for item in selected_items}
        filler_pool = [s for s in assigned if s["section_id"] not in selected_ids]

    benchmark_records: List[Dict[str, Any]] = []
    short_records: List[Dict[str, Any]] = []

    target_tokens_list = config.padding.target_tokens or [8000]
    primary_target_tokens = target_tokens_list[0]

    for item in selected_items:
        rep_id = item.get("report_id", "rep")
        s_idx = item.get("index", 0)
        cat = item.get("category", "ans")
        item_id = f"fab-{rep_id}-{s_idx:04d}-{cat[:3]}"

        ans = item.get("answer", "")
        edit_data = item.get("edit", {})
        conf_val = edit_data.get("conflicting_value", "")
        dist_val = edit_data.get("distractor_value", "")

        # Short value flag
        short_val_flag = any(0 < len(str(v).strip()) < 3 for v in [ans, conf_val, dist_val] if v)

        # Leakage guard: filter filler pool
        safe_fillers = []
        for f in filler_pool:
            f_text = f["text"]
            leak = False
            for v in [ans, conf_val, dist_val]:
                if v and len(str(v).strip()) >= 3 and answer_in_text(str(v), f_text):
                    leak = True
                    break
            if not leak:
                safe_fillers.append(f)

        if not safe_fillers:
            safe_fillers = filler_pool

        # Build padded context
        item_rng = random.Random(config.seed + 8000 + s_idx)
        context_str, target_pos, target_idx, approx_tokens = construct_padded_context(
            item_text=item.get("edited_text", item.get("text", "")),
            fillers=safe_fillers,
            target_tokens=primary_target_tokens,
            rng=item_rng
        )

        gold_dec = "answer" if cat == "answerable" else "abstain"
        gold_reas = "none" if cat == "answerable" else cat

        bench_record = {
            "id": item_id,
            "category": cat,
            "gold_decision": gold_dec,
            "gold_reason": gold_reas,
            "question": item.get("question_final", item.get("question")),
            "context": context_str,
            "gold_answer": ans if cat == "answerable" else None,
            "original_answer": ans,
            "evidence_span": item.get("evidence_span"),
            "fact_type": item.get("fact_type"),
            "report_id": rep_id,
            "section_id": item.get("section_id"),
            "target_position": round(target_pos, 4),
            "target_section_index": target_idx,
            "approx_tokens": approx_tokens,
            "edit": edit_data,
            "short_value_flag": short_val_flag,
            "needs_llm_validation": item.get("needs_llm_validation", False),
            "validator_a": item.get("validator_a"),
            "validator_b": item.get("validator_b"),
        }
        benchmark_records.append(bench_record)

        short_record = dict(bench_record)
        short_record["context"] = item.get("edited_text", item.get("text", ""))
        short_record["approx_tokens"] = count_tokens(short_record["context"])
        short_records.append(short_record)

    # Sort outputs by ID for stable diffs
    benchmark_records = sorted(benchmark_records, key=lambda x: x["id"])
    short_records = sorted(short_records, key=lambda x: x["id"])

    write_jsonl_atomic(bench_file, benchmark_records)
    write_jsonl_atomic(short_file, short_records)

    return [bench_file, short_file]
