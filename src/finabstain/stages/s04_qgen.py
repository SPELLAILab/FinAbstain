from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from ..config import AppConfig
from ..io_utils import read_jsonl, write_jsonl_atomic
from ..llm import LLMClient
from ..textnorm import normalize_text, answer_in_text
from ..stats import StatsTracker

def validate_qgen_output(sec_text: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if not isinstance(data, dict):
        return False, "invalid_json_format"

    question = str(data.get("question", "")).strip()
    answer = str(data.get("answer", "")).strip()
    evidence_span = str(data.get("evidence_span", "")).strip()

    if not question or not answer or not evidence_span:
        return False, "missing_required_fields"

    if evidence_span not in sec_text:
        return False, "evidence_span_not_in_text"

    if not answer_in_text(answer, evidence_span):
        return False, "answer_not_in_evidence"

    norm_ans = normalize_text(answer)
    norm_q = normalize_text(question)
    if norm_ans and norm_ans in norm_q:
        return False, "question_contains_answer"

    if len(question.split()) < 6:
        return False, "question_too_short"

    if "?" not in question:
        return False, "question_has_no_question_mark"

    return True, None

def run_stage(
    config: AppConfig,
    llm_client: LLMClient,
    stats: StatsTracker,
    force: bool = False,
    limit: Optional[int] = None
) -> Path:
    out_file = Path(config.data.out_dir) / "04_qgen.jsonl"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return out_file

    in_file = Path(config.data.out_dir) / "03_assigned.jsonl"
    assigned = read_jsonl(in_file)
    items = [s for s in assigned if s.get("role") == "item"]
    if limit is not None:
        items = items[:limit]

    # Resume capability: check what's already completed in partial out_file
    existing_records = {r["section_id"]: r for r in read_jsonl(out_file)} if not force and out_file.exists() else {}

    prompt_template = Path("prompts/qgen.txt").read_text(encoding="utf-8")
    results: List[Dict[str, Any]] = []

    for item in tqdm(items, desc="Stage 04: QGen"):
        sec_id = item["section_id"]
        if sec_id in existing_records:
            results.append(existing_records[sec_id])
            continue

        prompt = prompt_template.replace("{section_text}", item["text"])
        messages = [{"role": "user", "content": prompt}]

        raw, parsed, _ = llm_client.call_chat("generator", messages, json_format=True, stats_tracker=stats)

        is_valid, fail_reason = validate_qgen_output(item["text"], parsed or {})

        rec = dict(item)
        if is_valid and parsed:
            rec["question"] = parsed["question"].strip()
            rec["answer"] = parsed["answer"].strip()
            rec["evidence_span"] = parsed["evidence_span"].strip()
            rec["fact_type"] = parsed.get("fact_type", "other")
            rec["qgen_passed"] = True
            stats.record_pass("qgen")
        else:
            rec["question"] = None
            rec["answer"] = None
            rec["evidence_span"] = None
            rec["fact_type"] = None
            rec["qgen_passed"] = False
            rec["qgen_fail_reason"] = fail_reason or "unknown"
            stats.record_rejection(sec_id, "s04_qgen", fail_reason or "unknown", {"raw_output": raw})

        results.append(rec)

    write_jsonl_atomic(out_file, results)
    return out_file
