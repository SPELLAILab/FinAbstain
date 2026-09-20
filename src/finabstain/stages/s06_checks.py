from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any, Set

from ..config import AppConfig
from ..io_utils import read_jsonl, write_jsonl_atomic
from ..diffing import verify_diff
from ..textnorm import (
    normalize_text,
    answer_in_text,
    numbers_in,
    relative_diff,
    has_reconcile_words
)
from ..stats import StatsTracker

GENERIC_TERMS = {
    "company", "corporation", "inc", "ltd", "llc", "corp", "address",
    "statements", "controls", "procedures", "cybersecurity", "corporate governance",
    "board", "directors", "management", "exhibit", "exhibits", "report", "filing",
    "mark one", "smaller", "legal proceedings", "financial statements",
    "supplementary data", "related transactions"
}

def load_anonymization_entities(anon_dir: Path) -> Dict[str, Set[str]]:
    mapping_files = list(anon_dir.glob("*.mapping.json"))
    res: Dict[str, Set[str]] = {}
    for mf in mapping_files:
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
            rep_id = data.get("report_id", mf.stem.split(".")[0])
            ents = set(data.get("entity_replacements", {}).keys())
            # Exclude short words and generic English business terms
            ents = {e for e in ents if len(e) > 3 and e.lower() not in GENERIC_TERMS}
            res[rep_id] = ents
        except Exception:
            pass
    return res

def check_item(
    item: Dict[str, Any],
    config: AppConfig,
    report_entities: Set[str]
) -> List[str]:
    reasons: List[str] = []

    if not item.get("edit_passed"):
        reasons.append(item.get("edit_fail_reason") or "edit_not_passed")
        return reasons

    cat = item.get("category")
    text = item.get("text", "")
    edited_text = item.get("edited_text", "")
    question = item.get("question", "")
    question_final = item.get("question_final", "")
    answer = item.get("answer", "")
    edit = item.get("edit", {})

    # 1. Common checks
    # Diff check
    diff_ok, diff_err = verify_diff(text, edited_text, cat, edit)
    if not diff_ok:
        reasons.append(f"diff_verification_failed: {diff_err}")

    # Residue check
    for ent in report_entities:
        if ent.lower() in edited_text.lower():
            reasons.append(f"anonymization_residue_found: {ent}")
            break
        if ent.lower() in question_final.lower():
            reasons.append(f"anonymization_residue_in_question: {ent}")
            break

    # Question doesn't contain answer
    if answer_in_text(answer, question_final):
        reasons.append("question_final_contains_answer")

    # 2. Per-category checks
    if cat == "answerable":
        if text.strip() != edited_text.strip():
            reasons.append("answerable_text_modified")
        if not answer_in_text(answer, text):
            reasons.append("answer_not_in_answerable_text")

    elif cat == "missing":
        if answer_in_text(answer, edited_text):
            reasons.append("answer_still_in_missing_text")

        orig_w = len(text.split())
        edit_w = len(edited_text.split())
        ratio = edit_w / max(orig_w, 1)
        if ratio < config.checks.min_kept_ratio_missing:
            reasons.append(f"kept_ratio_{ratio:.2f}_below_min_{config.checks.min_kept_ratio_missing:.2f}")

    elif cat == "conflict":
        if not answer_in_text(answer, edited_text):
            reasons.append("original_answer_missing_from_conflict_text")

        conf_val = edit.get("conflicting_value", "")
        ins_text = edit.get("inserted_text", "")

        if not conf_val or conf_val not in ins_text:
            reasons.append("conflicting_value_not_in_inserted_text")

        if len(ins_text.split()) > config.checks.max_inserted_words:
            reasons.append("inserted_text_exceeds_max_words")

        if has_reconcile_words(ins_text):
            reasons.append("inserted_text_contains_reconcile_words")

        # Values must differ
        ans_nums = numbers_in(answer)
        conf_nums = numbers_in(conf_val)
        if ans_nums and conf_nums:
            rd = relative_diff(ans_nums[0], conf_nums[0])
            if rd < config.checks.conflict_min_rel_diff:
                reasons.append(f"conflict_relative_diff_{rd:.3f}_below_threshold")
        elif normalize_text(conf_val) == normalize_text(answer):
            reasons.append("conflicting_value_identical_to_answer")

    elif cat == "ambiguous":
        if not answer_in_text(answer, edited_text):
            reasons.append("original_answer_missing_from_ambiguous_text")

        dist_val = edit.get("distractor_value", "")
        ins_text = edit.get("inserted_text", "")
        removed_words = edit.get("removed_from_question", [])

        if not dist_val or dist_val not in ins_text:
            reasons.append("distractor_value_not_in_inserted_text")

        if len(ins_text.split()) > config.checks.max_inserted_words:
            reasons.append("inserted_text_exceeds_max_words")

        if has_reconcile_words(ins_text):
            reasons.append("inserted_text_contains_reconcile_words")

        # Distractor differs from answer
        ans_nums = numbers_in(answer)
        dist_nums = numbers_in(dist_val)
        if ans_nums and dist_nums:
            rd = relative_diff(ans_nums[0], dist_nums[0])
            if rd < config.checks.conflict_min_rel_diff:
                reasons.append(f"distractor_relative_diff_{rd:.3f}_below_threshold")
        elif normalize_text(dist_val) == normalize_text(answer):
            reasons.append("distractor_value_identical_to_answer")

        # Removed words check
        orig_q_norm = set(normalize_text(question).split())
        new_q_norm = set(normalize_text(question_final).split())

        for rw in removed_words:
            nrw = normalize_text(str(rw))
            if nrw and nrw not in orig_q_norm:
                reasons.append(f"removed_word_{rw}_not_in_orig_question")
            if nrw and nrw in new_q_norm:
                reasons.append(f"removed_word_{rw}_still_in_new_question")

        # New question content words check: new_q words must be subset of original question words
        # (ignoring minor stop words/formatting)
        for w in new_q_norm:
            if w not in orig_q_norm and len(w) > 3:
                reasons.append(f"new_question_introduces_novel_word_{w}")

        if answer_in_text(answer, question_final) or answer_in_text(dist_val, question_final):
            reasons.append("new_question_contains_answer_or_distractor")

    return reasons

def run_stage(config: AppConfig, stats: StatsTracker, force: bool = False) -> Path:
    out_file = Path(config.data.out_dir) / "06_checked.jsonl"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return out_file

    in_file = Path(config.data.out_dir) / "05_edits.jsonl"
    edits = read_jsonl(in_file)

    anon_dir = Path(config.data.out_dir) / "01_anonymized"
    report_entities_map = load_anonymization_entities(anon_dir)

    results: List[Dict[str, Any]] = []

    for item in edits:
        rep_id = item.get("report_id", "")
        ents = report_entities_map.get(rep_id, set())
        reasons = check_item(item, config, ents)

        rec = dict(item)
        passed = (len(reasons) == 0)
        rec["passed"] = passed
        rec["fail_reasons"] = reasons

        if passed:
            stats.record_pass("checked")
        else:
            stats.record_rejection(item["section_id"], "s06_checks", "; ".join(reasons))

        results.append(rec)

    write_jsonl_atomic(out_file, results)
    return out_file
