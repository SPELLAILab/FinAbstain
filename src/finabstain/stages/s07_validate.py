from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from ..config import AppConfig
from ..io_utils import read_jsonl, write_jsonl_atomic
from ..llm import LLMClient
from ..stats import StatsTracker

def run_stage(
    config: AppConfig,
    llm_client: LLMClient,
    stats: StatsTracker,
    force: bool = False,
    limit: Optional[int] = None
) -> Path:
    out_file = Path(config.data.out_dir) / "07_validated.jsonl"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return out_file

    in_file = Path(config.data.out_dir) / "06_checked.jsonl"
    checked_records = read_jsonl(in_file)
    passed_items = [r for r in checked_records if r.get("passed")]
    if limit is not None:
        passed_items = passed_items[:limit]

    existing_records = {r["section_id"]: r for r in read_jsonl(out_file)} if not force and out_file.exists() else {}

    taxonomy_text = Path("prompts/taxonomy.txt").read_text(encoding="utf-8").strip()
    validate_template = Path("prompts/validate.txt").read_text(encoding="utf-8")
    full_prompt_tmpl = validate_template.replace("{taxonomy}", taxonomy_text)

    results: List[Dict[str, Any]] = []

    for item in tqdm(passed_items, desc="Stage 07: Validate (A & B)"):
        sec_id = item["section_id"]
        if sec_id in existing_records:
            results.append(existing_records[sec_id])
            continue

        q_val = item.get("question_final", item.get("question", ""))
        sec_val = item.get("edited_text", item.get("text", ""))
        prompt = full_prompt_tmpl.replace("{question}", q_val).replace("{section_text}", sec_val)
        messages = [{"role": "user", "content": prompt}]

        # Call Validator A
        raw_a, parsed_a, _ = llm_client.call_chat("validator_a", messages, json_format=True, stats_tracker=stats)
        # Call Validator B
        raw_b, parsed_b, _ = llm_client.call_chat("validator_b", messages, json_format=True, stats_tracker=stats)

        label_a = str(parsed_a.get("label", "")).strip().lower() if parsed_a else "error"
        label_b = str(parsed_b.get("label", "")).strip().lower() if parsed_b else "error"

        gold_cat = item.get("category", "")
        both_matched = (label_a == gold_cat and label_b == gold_cat)

        rec = dict(item)
        rec["validator_a"] = {
            "model": config.llm.models.get("validator_a", {}).name if hasattr(config.llm.models.get("validator_a"), "name") else "validator_a",
            "label": label_a,
            "answer": parsed_a.get("answer", "") if parsed_a else "",
            "rationale": parsed_a.get("rationale", "") if parsed_a else (raw_a or "")[:100],
        }
        rec["validator_b"] = {
            "model": config.llm.models.get("validator_b", {}).name if hasattr(config.llm.models.get("validator_b"), "name") else "validator_b",
            "label": label_b,
            "answer": parsed_b.get("answer", "") if parsed_b else "",
            "rationale": parsed_b.get("rationale", "") if parsed_b else (raw_b or "")[:100],
        }
        rec["validated"] = both_matched
        rec["needs_llm_validation"] = (gold_cat == "ambiguous")

        if both_matched:
            stats.record_pass("validated")
        else:
            stats.record_rejection(
                sec_id,
                "s07_validate",
                f"validation_mismatch: gold={gold_cat}, A={label_a}, B={label_b}"
            )

        results.append(rec)

    write_jsonl_atomic(out_file, results)

    # Compute validation statistics and store in stats tracker
    val_stats = stats.compute_validation_stats(results)
    stats.save(Path(config.data.out_dir) / "stats.json", extra={"validation_metrics": val_stats})

    return out_file
