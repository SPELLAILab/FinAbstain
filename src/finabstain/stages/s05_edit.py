from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm

from ..config import AppConfig
from ..io_utils import read_jsonl, write_jsonl_atomic
from ..llm import LLMClient
from ..diffing import apply_deletion, apply_insertion, deterministic_missing_fallback
from ..textnorm import normalize_text, answer_in_text, numbers_in, relative_diff, has_reconcile_words
from ..stats import StatsTracker

def attempt_missing_edit(
    text: str,
    question: str,
    answer: str,
    template: str,
    llm_client: LLMClient,
    stats: StatsTracker,
    min_kept_ratio: float
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    orig_words = len(text.split())
    prompt_str = template.replace("{question}", question).replace("{answer}", answer).replace("{section_text}", text)
    messages = [{"role": "user", "content": prompt_str}]

    for attempt in range(3):
        raw, parsed, _ = llm_client.call_chat("generator", messages, json_format=True, stats_tracker=stats)
        if not parsed or "deletions" not in parsed:
            err = "Invalid JSON or missing 'deletions' field"
        else:
            deletions = parsed.get("deletions", [])
            edited, err = apply_deletion(text, deletions)
            if not err and edited:
                # Check kept ratio
                kept_ratio = len(edited.split()) / max(orig_words, 1)
                if kept_ratio < min_kept_ratio:
                    err = f"Deleted too much text: kept ratio {kept_ratio:.2f} < {min_kept_ratio:.2f}"
                elif answer_in_text(answer, edited):
                    err = f"Answer '{answer}' is still present in the text after deletion"
                else:
                    return edited, {"deletions": deletions}, None

        # Prepare retry message
        if attempt < 2:
            messages.append({"role": "assistant", "content": raw or "{}"})
            messages.append({"role": "user", "content": f"The edit failed validation: {err}. Please fix it and return valid JSON with verbatim deletions."})

    # Deterministic fallback for missing
    fb_text, fb_edit, fb_err = deterministic_missing_fallback(text, answer, min_kept_ratio)
    if fb_text:
        return fb_text, fb_edit, None

    return None, None, err or fb_err or "Missing edit failed"

def attempt_conflict_edit(
    text: str,
    question: str,
    answer: str,
    template: str,
    llm_client: LLMClient,
    stats: StatsTracker,
    max_inserted_words: int,
    min_rel_diff: float
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    prompt_str = template.replace("{question}", question).replace("{answer}", answer).replace("{section_text}", text)
    messages = [{"role": "user", "content": prompt_str}]

    for attempt in range(3):
        raw, parsed, _ = llm_client.call_chat("generator", messages, json_format=True, stats_tracker=stats)
        if not parsed or not all(k in parsed for k in ("anchor", "inserted_text", "conflicting_value")):
            err = "Missing required keys: anchor, inserted_text, conflicting_value"
        else:
            anchor = str(parsed["anchor"]).strip()
            ins_text = str(parsed["inserted_text"]).strip()
            conf_val = str(parsed["conflicting_value"]).strip()

            if len(ins_text.split()) > max_inserted_words:
                err = f"Inserted text has {len(ins_text.split())} words, max allowed is {max_inserted_words}"
            elif has_reconcile_words(ins_text):
                err = "Inserted text contains forbidden reconciliation words"
            elif conf_val not in ins_text:
                err = "conflicting_value not found inside inserted_text"
            else:
                # Value difference check
                ans_nums = numbers_in(answer)
                conf_nums = numbers_in(conf_val)
                if ans_nums and conf_nums:
                    rd = relative_diff(ans_nums[0], conf_nums[0])
                    if rd < min_rel_diff:
                        err = f"Conflicting value {conf_val} relative difference {rd:.3f} < {min_rel_diff}"
                    else:
                        edited, err = apply_insertion(text, anchor, ins_text)
                        if not err and edited:
                            return edited, parsed, None
                else:
                    if normalize_text(conf_val) == normalize_text(answer):
                        err = "Conflicting value is identical to original answer"
                    else:
                        edited, err = apply_insertion(text, anchor, ins_text)
                        if not err and edited:
                            return edited, parsed, None

        if attempt < 2:
            messages.append({"role": "assistant", "content": raw or "{}"})
            messages.append({"role": "user", "content": f"The edit failed validation: {err}. Please return valid JSON."})

    return None, None, err or "Conflict edit failed"

def attempt_ambiguous_edit(
    text: str,
    question: str,
    answer: str,
    template: str,
    llm_client: LLMClient,
    stats: StatsTracker,
    max_inserted_words: int,
    min_rel_diff: float
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    prompt_str = template.replace("{question}", question).replace("{answer}", answer).replace("{section_text}", text)
    messages = [{"role": "user", "content": prompt_str}]

    for attempt in range(3):
        raw, parsed, _ = llm_client.call_chat("generator", messages, json_format=True, stats_tracker=stats)
        req_keys = ("anchor", "inserted_text", "distractor_value", "blurred_dimension", "new_question", "removed_from_question")
        if not parsed or not all(k in parsed for k in req_keys):
            err = "Missing required keys for ambiguous edit"
        else:
            anchor = str(parsed["anchor"]).strip()
            ins_text = str(parsed["inserted_text"]).strip()
            dist_val = str(parsed["distractor_value"]).strip()
            new_q = str(parsed["new_question"]).strip()
            removed_words = parsed.get("removed_from_question", [])

            if len(ins_text.split()) > max_inserted_words:
                err = f"Inserted text exceeds {max_inserted_words} words"
            elif has_reconcile_words(ins_text):
                err = "Inserted text contains reconciliation words"
            elif dist_val not in ins_text:
                err = "distractor_value not in inserted_text"
            elif answer_in_text(answer, new_q) or answer_in_text(dist_val, new_q):
                err = "new_question contains answer or distractor value"
            else:
                # Check removed words
                q_words = set(normalize_text(question).split())
                new_q_words = set(normalize_text(new_q).split())
                rm_valid = True
                for rw in removed_words:
                    norm_rw = normalize_text(str(rw))
                    if norm_rw and norm_rw not in q_words:
                        err = f"Word '{rw}' in removed_from_question was not in original question"
                        rm_valid = False
                        break
                    if norm_rw and norm_rw in new_q_words:
                        err = f"Word '{rw}' still appears in new_question"
                        rm_valid = False
                        break

                if rm_valid:
                    edited, err = apply_insertion(text, anchor, ins_text)
                    if not err and edited:
                        return edited, new_q, parsed, None

        if attempt < 2:
            messages.append({"role": "assistant", "content": raw or "{}"})
            messages.append({"role": "user", "content": f"The edit failed validation: {err}. Please return valid JSON."})

    return None, None, None, err or "Ambiguous edit failed"

def run_stage(
    config: AppConfig,
    llm_client: LLMClient,
    stats: StatsTracker,
    force: bool = False,
    limit: Optional[int] = None
) -> Path:
    out_file = Path(config.data.out_dir) / "05_edits.jsonl"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return out_file

    in_file = Path(config.data.out_dir) / "04_qgen.jsonl"
    qgen_records = read_jsonl(in_file)
    valid_items = [r for r in qgen_records if r.get("qgen_passed")]
    if limit is not None:
        valid_items = valid_items[:limit]

    existing_records = {r["section_id"]: r for r in read_jsonl(out_file)} if not force and out_file.exists() else {}

    tmpl_missing = Path("prompts/edit_missing.txt").read_text(encoding="utf-8")
    tmpl_conflict = Path("prompts/edit_conflict.txt").read_text(encoding="utf-8")
    tmpl_ambiguous = Path("prompts/edit_ambiguous.txt").read_text(encoding="utf-8")

    results: List[Dict[str, Any]] = []

    for item in tqdm(valid_items, desc="Stage 05: Apply Edits"):
        sec_id = item["section_id"]
        if sec_id in existing_records:
            results.append(existing_records[sec_id])
            continue

        cat = item["category"]
        text = item["text"]
        question = item["question"]
        answer = item["answer"]

        rec = dict(item)
        rec["edit_passed"] = False

        if cat == "answerable":
            rec["edited_text"] = text
            rec["question_final"] = question
            rec["edit"] = {}
            rec["edit_passed"] = True
            stats.record_pass("edit_answerable")

        elif cat == "missing":
            edited, edit_data, err = attempt_missing_edit(
                text=text,
                question=question,
                answer=answer,
                template=tmpl_missing,
                llm_client=llm_client,
                stats=stats,
                min_kept_ratio=config.checks.min_kept_ratio_missing
            )
            if edited and edit_data:
                rec["edited_text"] = edited
                rec["question_final"] = question
                rec["edit"] = edit_data
                rec["edit_passed"] = True
                stats.record_pass("edit_missing")
            else:
                rec["edit_fail_reason"] = err
                stats.record_rejection(sec_id, "s05_edit_missing", err or "unknown")

        elif cat == "conflict":
            edited, edit_data, err = attempt_conflict_edit(
                text=text,
                question=question,
                answer=answer,
                template=tmpl_conflict,
                llm_client=llm_client,
                stats=stats,
                max_inserted_words=config.checks.max_inserted_words,
                min_rel_diff=config.checks.conflict_min_rel_diff
            )
            if edited and edit_data:
                rec["edited_text"] = edited
                rec["question_final"] = question
                rec["edit"] = edit_data
                rec["edit_passed"] = True
                stats.record_pass("edit_conflict")
            else:
                rec["edit_fail_reason"] = err
                stats.record_rejection(sec_id, "s05_edit_conflict", err or "unknown")

        elif cat == "ambiguous":
            edited, new_q, edit_data, err = attempt_ambiguous_edit(
                text=text,
                question=question,
                answer=answer,
                template=tmpl_ambiguous,
                llm_client=llm_client,
                stats=stats,
                max_inserted_words=config.checks.max_inserted_words,
                min_rel_diff=config.checks.conflict_min_rel_diff
            )
            if edited and new_q and edit_data:
                rec["edited_text"] = edited
                rec["question_final"] = new_q
                rec["edit"] = edit_data
                rec["edit_passed"] = True
                stats.record_pass("edit_ambiguous")
            else:
                rec["edit_fail_reason"] = err
                stats.record_rejection(sec_id, "s05_edit_ambiguous", err or "unknown")

        results.append(rec)

    write_jsonl_atomic(out_file, results)
    return out_file
