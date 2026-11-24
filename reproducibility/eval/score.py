#!/usr/bin/env python3
"""
FinAbstain Scoring Harness: computes benchmark metrics, confidence intervals, baselines, and robustness subsets.
Requires only standard library and numpy (no sklearn).
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

import numpy as np

ALLOWED_CATEGORIES = ["answerable", "missing", "conflict", "ambiguous"]
ALLOWED_DECISIONS = {"answer", "abstain"}
ALLOWED_REASONS = {"none", "missing", "conflict", "ambiguous"}

def extract_balanced_json_objects(text: str) -> List[str]:
    """Finds all balanced {...} JSON objects from text."""
    if not text:
        return []
    objects = []
    i = 0
    n = len(text)
    while i < n:
        start = text.find("{", i)
        if start == -1:
            break
        depth = 0
        in_string = False
        escape = False
        end = -1
        for j in range(start, n):
            ch = text[j]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
        if end != -1:
            objects.append(text[start : end + 1])
            i = end + 1
        else:
            i = start + 1
    return objects

def extract_first_balanced_json(text: str) -> Optional[str]:
    """Finds the most relevant balanced {...} JSON object containing 'decision'."""
    objs = extract_balanced_json_objects(text)
    for obj in objs:
        if '"decision"' in obj:
            return obj
    return objs[0] if objs else None

def normalize_text_for_answer(text: str) -> str:
    """
    Normalizes text for answer comparison:
    lowercase, strip $, commas, spaces, trailing periods; (340) -> -340; 12.5 % -> 12.5%
    """
    if not text:
        return ""
    s = text.lower().strip()
    s = s.replace("$", "").replace(",", "")
    s = re.sub(r"\(([0-9.]+)\)", r"-\1", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1%", s)
    s = s.rstrip(".")
    # Collapse multiple whitespace
    s = " ".join(s.split())
    return s

def parse_numeric_val(text: str) -> Optional[float]:
    """
    Extracts a numeric float value supporting multipliers:
    $1.2 million -> 1,200,000; 1.2M -> 1,200,000; (340) -> -340; 12.5% -> 12.5
    """
    if not text:
        return None
    s = normalize_text_for_answer(text)
    m = re.search(r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(million|billion|thousand|m|b|k|%)?", s)
    if not m:
        return None
    num_str, unit = m.groups()
    try:
        val = float(num_str)
    except ValueError:
        return None
    mult = 1.0
    if unit:
        u = unit.lower()
        if u in ("million", "m"):
            mult = 1e6
        elif u in ("billion", "b"):
            mult = 1e9
        elif u in ("thousand", "k"):
            mult = 1e3
    return val * mult

def compute_answer_em_and_f1(gold_answer: str, pred_answer: str, pred_decision: str) -> Tuple[float, float]:
    """
    Computes answer EM and Token-F1 on answerable items.
    EM is true if normalized strings match, or normalized gold string is contained in prediction,
    or parsed numeric values are equal.
    Token-F1 is computed from word overlap of normalized strings.
    """
    if pred_decision != "answer" or not pred_answer:
        return 0.0, 0.0

    norm_gold = normalize_text_for_answer(gold_answer)
    norm_pred = normalize_text_for_answer(pred_answer)

    # Check numeric equivalence
    gold_num = parse_numeric_val(gold_answer)
    pred_num = parse_numeric_val(pred_answer)
    num_match = False
    if gold_num is not None and pred_num is not None:
        if abs(gold_num - pred_num) < 1e-4 or (abs(gold_num) > 1e-9 and abs(gold_num - pred_num) / abs(gold_num) < 1e-4):
            num_match = True

    # Check string match or substring inclusion
    str_match = (norm_gold == norm_pred) or (norm_gold and norm_gold in norm_pred)

    em = 1.0 if (num_match or str_match) else 0.0
    if em == 1.0:
        return 1.0, 1.0

    # Token F1
    gold_tokens = norm_gold.split()
    pred_tokens = norm_pred.split()

    if not gold_tokens and not pred_tokens:
        f1 = 1.0
    elif not gold_tokens or not pred_tokens:
        f1 = 0.0
    else:
        common = Counter(gold_tokens) & Counter(pred_tokens)
        num_same = sum(common.values())
        if num_same == 0:
            f1 = 0.0
        else:
            precision = num_same / len(pred_tokens)
            recall = num_same / len(gold_tokens)
            f1 = (2 * precision * recall) / (precision + recall)

    return em, f1

def parse_model_output(record: Dict[str, Any]) -> Tuple[str, str, str, bool]:
    """
    Parses model completion record from raw.jsonl.
    Returns (pred_decision, pred_reason, pred_answer, is_parse_fail).
    A parse_fail is scored wrong on every metric (pred_label = PARSE_FAIL).
    """
    if record.get("error"):
        return "PARSE_FAIL", "PARSE_FAIL", "", True

    raw_text = record.get("raw_text", "")
    # Strip <think> blocks
    clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
    if "<think>" in clean_text:
        clean_text = re.sub(r"<think>.*", "", clean_text, flags=re.DOTALL)
    clean_text = clean_text.strip()

    json_str = extract_first_balanced_json(clean_text)
    if not json_str:
        # Fallback: regex search for key-value pairs in markdown
        dec_m = re.search(r"[*_\s]*decision[*_\s]*:?\s*[*_`]*(\banswer\b|\babstain\b)", clean_text, re.I)
        reas_m = re.search(r"[*_\s]*reason[*_\s]*:?\s*[*_`]*(\bnone\b|\bmissing\b|\bconflict\b|\bambiguous\b)", clean_text, re.I)
        ans_m = re.search(r"[*_\s]*answer[*_\s]*:?\s*[*_`]*(.*?)(?:\n|$)", clean_text, re.I)
        if dec_m:
            decision = dec_m.group(1).lower()
            reason = reas_m.group(1).lower() if reas_m else ("none" if decision == "answer" else "missing")
            answer = ans_m.group(1).strip(" *`\"") if ans_m else ""
            if decision == "answer" and reason == "none":
                return decision, "answerable", answer, False
            elif decision == "abstain" and reason in {"missing", "conflict", "ambiguous"}:
                return decision, reason, "", False
        return "PARSE_FAIL", "PARSE_FAIL", "", True

    try:
        data = json.loads(json_str)
    except Exception:
        return "PARSE_FAIL", "PARSE_FAIL", "", True

    if not isinstance(data, dict):
        return "PARSE_FAIL", "PARSE_FAIL", "", True

    decision = str(data.get("decision", "")).strip().lower()
    reason = str(data.get("reason", "")).strip().lower()
    answer = str(data.get("answer", "")).strip()

    if decision not in ALLOWED_DECISIONS:
        return "PARSE_FAIL", "PARSE_FAIL", "", True

    if reason not in ALLOWED_REASONS:
        return "PARSE_FAIL", "PARSE_FAIL", "", True

    # Consistency checks:
    # If decision is "answer", reason must be "none"
    if decision == "answer" and reason != "none":
        return "PARSE_FAIL", "PARSE_FAIL", "", True
    # If decision is "abstain", reason must be one of missing, conflict, ambiguous
    if decision == "abstain" and reason not in {"missing", "conflict", "ambiguous"}:
        return "PARSE_FAIL", "PARSE_FAIL", "", True

    pred_reason = "answerable" if decision == "answer" else reason
    pred_answer = answer if decision == "answer" else ""

    return decision, pred_reason, pred_answer, False

def compute_metrics_vectorized(
    gold_categories: List[str],
    pred_reasons: List[str],
    pred_decisions: List[str],
    gold_answers: List[str],
    pred_answers: List[str],
    is_parse_fails: List[bool],
    categories: List[str] = ALLOWED_CATEGORIES,
) -> Dict[str, float]:
    """Computes all primary evaluation metrics over a given set of items."""
    n = len(gold_categories)
    if n == 0:
        return {
            "reason_macro_f1": 0.0,
            "decision_accuracy": 0.0,
            "over_refusal_rate": 0.0,
            "over_answer_rate": 0.0,
            "answer_em": 0.0,
            "answer_f1": 0.0,
            "parse_fail_rate": 0.0,
        }

    # 1. Reason Macro-F1
    f1_list = []
    for c in categories:
        tp = sum(1 for g, p in zip(gold_categories, pred_reasons) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold_categories, pred_reasons) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold_categories, pred_reasons) if g == c and p != c)
        support = tp + fn
        if support == 0:
            continue
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_list.append(f1)

    macro_f1 = float(np.mean(f1_list)) if f1_list else 0.0

    # 2. Decision Accuracy (answer vs abstain)
    gold_decisions = ["answer" if g == "answerable" else "abstain" for g in gold_categories]
    dec_correct = sum(1 for gd, pd in zip(gold_decisions, pred_decisions) if gd == pd)
    decision_acc = dec_correct / n

    # 3. Over-refusal rate: fraction of answerable items where model abstains (or parse_fail)
    ans_indices = [i for i, g in enumerate(gold_categories) if g == "answerable"]
    if ans_indices:
        over_refusals = sum(1 for i in ans_indices if pred_decisions[i] != "answer")
        over_refusal_rate = over_refusals / len(ans_indices)
    else:
        over_refusal_rate = 0.0

    # 4. Over-answer rate: fraction of unanswerable items where model answers
    unans_indices = [i for i, g in enumerate(gold_categories) if g != "answerable"]
    if unans_indices:
        over_answers = sum(1 for i in unans_indices if pred_decisions[i] == "answer")
        over_answer_rate = over_answers / len(unans_indices)
    else:
        over_answer_rate = 0.0

    # 5. Answer EM and Token-F1 (on answerable items only)
    if ans_indices:
        em_vals = []
        f1_vals = []
        for i in ans_indices:
            em, af1 = compute_answer_em_and_f1(gold_answers[i], pred_answers[i], pred_decisions[i])
            em_vals.append(em)
            f1_vals.append(af1)
        answer_em = float(np.mean(em_vals))
        answer_f1 = float(np.mean(f1_vals))
    else:
        answer_em = 0.0
        answer_f1 = 0.0

    # 6. Parse-fail rate
    parse_fail_rate = sum(1 for pf in is_parse_fails if pf) / n

    return {
        "reason_macro_f1": macro_f1,
        "decision_accuracy": decision_acc,
        "over_refusal_rate": over_refusal_rate,
        "over_answer_rate": over_answer_rate,
        "answer_em": answer_em,
        "answer_f1": answer_f1,
        "parse_fail_rate": parse_fail_rate,
    }

def bootstrap_confidence_intervals(
    gold_categories: List[str],
    pred_reasons: List[str],
    pred_decisions: List[str],
    gold_answers: List[str],
    pred_answers: List[str],
    is_parse_fails: List[bool],
    seed: int = 42,
    n_resamples: int = 1000,
) -> Dict[str, Tuple[float, float]]:
    """Computes 95% bootstrap confidence intervals for primary metrics."""
    rng = np.random.RandomState(seed)
    n = len(gold_categories)
    metric_keys = [
        "reason_macro_f1",
        "decision_accuracy",
        "over_refusal_rate",
        "over_answer_rate",
        "answer_em",
        "answer_f1",
        "parse_fail_rate",
    ]
    sampled_values: Dict[str, List[float]] = {k: [] for k in metric_keys}

    for _ in range(n_resamples):
        indices = rng.randint(0, n, size=n)
        sub_gold_cats = [gold_categories[i] for i in indices]
        sub_pred_reasons = [pred_reasons[i] for i in indices]
        sub_pred_decisions = [pred_decisions[i] for i in indices]
        sub_gold_answers = [gold_answers[i] for i in indices]
        sub_pred_answers = [pred_answers[i] for i in indices]
        sub_parse_fails = [is_parse_fails[i] for i in indices]

        m = compute_metrics_vectorized(
            sub_gold_cats,
            sub_pred_reasons,
            sub_pred_decisions,
            sub_gold_answers,
            sub_pred_answers,
            sub_parse_fails,
        )
        for k in metric_keys:
            sampled_values[k].append(m[k])

    cis = {}
    for k in metric_keys:
        lo = float(np.percentile(sampled_values[k], 2.5))
        hi = float(np.percentile(sampled_values[k], 97.5))
        cis[k] = (round(lo, 4), round(hi, 4))
    return cis

def compute_per_category_stats(
    gold_categories: List[str], pred_reasons: List[str]
) -> List[Dict[str, Any]]:
    """Calculates support, precision, recall, and F1 for each category."""
    rows = []
    for c in ALLOWED_CATEGORIES:
        tp = sum(1 for g, p in zip(gold_categories, pred_reasons) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold_categories, pred_reasons) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold_categories, pred_reasons) if g == c and p != c)
        support = tp + fn
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        rows.append({
            "category": c,
            "support": support,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        })
    return rows

def compute_confusion_matrix(
    gold_categories: List[str], pred_reasons: List[str]
) -> List[Dict[str, Any]]:
    """Builds 4x4 confusion matrix (+ PARSE_FAIL column)."""
    cols = ALLOWED_CATEGORIES + ["PARSE_FAIL"]
    rows = []
    for g in ALLOWED_CATEGORIES:
        row_dict: Dict[str, Any] = {"gold_category": g}
        sub_preds = [p for gold, p in zip(gold_categories, pred_reasons) if gold == g]
        total_g = len(sub_preds)
        for col in cols:
            cnt = sum(1 for p in sub_preds if p == col)
            pct = (cnt / total_g * 100) if total_g > 0 else 0.0
            row_dict[f"pred_{col}"] = cnt
            row_dict[f"pct_{col}"] = round(pct, 1)
        row_dict["total"] = total_g
        rows.append(row_dict)
    return rows

def compute_baselines(
    gold_categories: List[str],
    gold_answers: List[str],
    seed: int = 42,
) -> Dict[str, Dict[str, Any]]:
    """Computes always-answer, always-abstain, and random-uniform baselines with bootstrap CIs."""
    n = len(gold_categories)
    baselines: Dict[str, Dict[str, Any]] = {}

    # 1. Always Answer
    aa_pred_dec = ["answer"] * n
    aa_pred_reas = ["answerable"] * n
    aa_pred_ans = [""] * n
    aa_pf = [False] * n
    aa_m = compute_metrics_vectorized(gold_categories, aa_pred_reas, aa_pred_dec, gold_answers, aa_pred_ans, aa_pf)
    aa_ci = bootstrap_confidence_intervals(gold_categories, aa_pred_reas, aa_pred_dec, gold_answers, aa_pred_ans, aa_pf, seed=seed)
    baselines["always_answer"] = {"metrics": aa_m, "ci_95": aa_ci}

    # 2. Always Abstain (reason=missing)
    ab_pred_dec = ["abstain"] * n
    ab_pred_reas = ["missing"] * n
    ab_pred_ans = [""] * n
    ab_pf = [False] * n
    ab_m = compute_metrics_vectorized(gold_categories, ab_pred_reas, ab_pred_dec, gold_answers, ab_pred_ans, ab_pf)
    ab_ci = bootstrap_confidence_intervals(gold_categories, ab_pred_reas, ab_pred_dec, gold_answers, ab_pred_ans, ab_pf, seed=seed)
    baselines["always_abstain"] = {"metrics": ab_m, "ci_95": ab_ci}

    # 3. Random Uniform (average over 100 draws)
    rng = np.random.RandomState(seed)
    metric_keys = list(aa_m.keys())
    ru_runs: Dict[str, List[float]] = {k: [] for k in metric_keys}

    for _ in range(100):
        rand_reasons = [rng.choice(ALLOWED_CATEGORIES) for _ in range(n)]
        rand_dec = ["answer" if r == "answerable" else "abstain" for r in rand_reasons]
        rand_ans = [""] * n
        rand_pf = [False] * n
        rm = compute_metrics_vectorized(gold_categories, rand_reasons, rand_dec, gold_answers, rand_ans, rand_pf)
        for k in metric_keys:
            ru_runs[k].append(rm[k])

    avg_ru = {k: float(np.mean(ru_runs[k])) for k in metric_keys}
    # Resample CI on the average random policy
    ru_ci = {k: (round(float(np.percentile(ru_runs[k], 2.5)), 4), round(float(np.percentile(ru_runs[k], 97.5)), 4)) for k in metric_keys}
    baselines["random_uniform"] = {"metrics": avg_ru, "ci_95": ru_ci}

    return baselines

def evaluate_model_run(
    dataset_items: List[Dict[str, Any]],
    raw_records: List[Dict[str, Any]],
    seed: int = 42,
) -> Dict[str, Any]:
    """Scores a single model run against dataset items."""
    raw_map = {r["id"]: r for r in raw_records if "id" in r}

    matched_items = []
    gold_categories = []
    gold_answers = []
    pred_decisions = []
    pred_reasons = []
    pred_answers = []
    is_parse_fails = []
    source_reports = []
    needs_validation_flags = []

    for item in dataset_items:
        i_id = item["id"]
        matched_items.append(item)
        gold_categories.append(item["category"])
        gold_answers.append(item.get("gold_answer") or "")
        source_reports.append(item.get("source_report", item.get("report_id", "unknown")))
        needs_validation_flags.append(item.get("needs_llm_validation", False))

        if i_id in raw_map:
            rec = raw_map[i_id]
            p_dec, p_reas, p_ans, pf = parse_model_output(rec)
        else:
            # Missing record counts as parse_fail
            p_dec, p_reas, p_ans, pf = "PARSE_FAIL", "PARSE_FAIL", "", True

        pred_decisions.append(p_dec)
        pred_reasons.append(p_reas)
        pred_answers.append(p_ans)
        is_parse_fails.append(pf)

    # 1. Overall metrics & CIs
    metrics = compute_metrics_vectorized(
        gold_categories, pred_reasons, pred_decisions, gold_answers, pred_answers, is_parse_fails
    )
    cis = bootstrap_confidence_intervals(
        gold_categories, pred_reasons, pred_decisions, gold_answers, pred_answers, is_parse_fails, seed=seed
    )

    # 2. Per-category stats
    per_category = compute_per_category_stats(gold_categories, pred_reasons)

    # 3. Confusion matrix
    confusion = compute_confusion_matrix(gold_categories, pred_reasons)

    # 4. Robustness subset (a): Deterministic only (needs_llm_validation == False)
    det_indices = [i for i, v in enumerate(needs_validation_flags) if not v]
    if det_indices:
        det_m = compute_metrics_vectorized(
            [gold_categories[i] for i in det_indices],
            [pred_reasons[i] for i in det_indices],
            [pred_decisions[i] for i in det_indices],
            [gold_answers[i] for i in det_indices],
            [pred_answers[i] for i in det_indices],
            [is_parse_fails[i] for i in det_indices],
        )
        det_subset = {
            "n": len(det_indices),
            "decision_accuracy": round(det_m["decision_accuracy"], 4),
            "reason_macro_f1": round(det_m["reason_macro_f1"], 4),
        }
    else:
        det_subset = {"n": 0, "decision_accuracy": 0.0, "reason_macro_f1": 0.0}

    # 5. Robustness subset (b): Per-company breakdown
    company_groups = defaultdict(list)
    for idx, rep in enumerate(source_reports):
        # Normalize report name if 'report'
        norm_rep = "amzn" if rep == "report" else rep
        company_groups[norm_rep].append(idx)

    per_company = []
    for comp, idxs in sorted(company_groups.items()):
        comp_m = compute_metrics_vectorized(
            [gold_categories[i] for i in idxs],
            [pred_reasons[i] for i in idxs],
            [pred_decisions[i] for i in idxs],
            [gold_answers[i] for i in idxs],
            [pred_answers[i] for i in idxs],
            [is_parse_fails[i] for i in idxs],
        )
        per_company.append({
            "source_report": comp,
            "n": len(idxs),
            "decision_accuracy": round(comp_m["decision_accuracy"], 4),
            "reason_macro_f1": round(comp_m["reason_macro_f1"], 4),
        })

    return {
        "metrics": metrics,
        "ci_95": cis,
        "per_category": per_category,
        "confusion_matrix": confusion,
        "robustness": {
            "deterministic_only": det_subset,
            "per_company": per_company,
        },
        "gold_categories": gold_categories,
        "gold_answers": gold_answers,
    }

def format_ci(val: float, ci: Tuple[float, float], pct: bool = False) -> str:
    """Formats a metric value and its 95% CI."""
    if pct:
        return f"{val*100:.1f} [{ci[0]*100:.1f}, {ci[1]*100:.1f}]"
    return f"{val:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]"

def main():
    parser = argparse.ArgumentParser(description="FinAbstain Scoring Harness")
    parser.add_argument("--data", default="release/benchmark.jsonl", help="Path to benchmark JSONL")
    parser.add_argument("--raw", nargs="+", default=None, help="Path(s) to raw.jsonl from one or more model runs")
    parser.add_argument("--input-dir", default=None, help="Input directory containing raw.jsonl (alternative to --raw)")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: parent of first --raw)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for bootstrap resampling")

    args = parser.parse_args()

    if not args.raw and not args.input_dir:
        parser.error("At least one of --raw or --input-dir is required")

    if args.input_dir and not args.raw:
        in_dir = Path(args.input_dir)
        raw_target = in_dir / "raw.jsonl"
        if not raw_target.exists():
            parser.error(f"Could not find raw.jsonl inside input directory: {in_dir}")
        args.raw = [str(raw_target)]
        if not args.out_dir:
            args.out_dir = str(in_dir)

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Benchmark dataset file not found: {data_path}")

    # Read benchmark dataset
    dataset_items = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                dataset_items.append(json.loads(line.strip()))

    first_raw = Path(args.raw[0])
    out_dir = Path(args.out_dir) if args.out_dir else first_raw.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("FINABSTAIN BENCHMARK SCORING")
    print("=" * 70)
    print(f"Dataset items:   {len(dataset_items)} from {data_path}")
    print(f"Output directory: {out_dir}")
    print(f"Raw file(s):      {args.raw}")
    print(f"Bootstrap seed:   {args.seed}")

    # Compute Baselines once
    gold_cats = [item["category"] for item in dataset_items]
    gold_ans = [item.get("gold_answer") or "" for item in dataset_items]
    baselines = compute_baselines(gold_cats, gold_ans, seed=args.seed)

    all_models_results: Dict[str, Any] = {}
    csv_rows: List[Dict[str, Any]] = []
    latex_rows: List[str] = []

    for raw_path_str in args.raw:
        raw_path = Path(raw_path_str)
        if not raw_path.exists():
            print(f"[WARNING] Raw file not found, skipping: {raw_path}")
            continue

        # Determine model name
        model_name = raw_path.parent.name
        manifest_file = raw_path.parent / "manifest.json"
        if manifest_file.exists():
            try:
                m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                model_name = m_data.get("model_name", model_name)
            except Exception:
                pass

        print(f"\nEvaluating model run: {model_name} ({raw_path})")

        raw_records = []
        with open(raw_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        raw_records.append(json.loads(line.strip()))
                    except Exception:
                        pass

        raw_ids = {r.get("id") for r in raw_records if "id" in r}
        if len(raw_ids) < len(dataset_items) and raw_ids.issubset({it["id"] for it in dataset_items}):
            eval_dataset = [it for it in dataset_items if it["id"] in raw_ids]
            print(f"  [INFO] Scoring evaluated subset: {len(eval_dataset)} items (smoke/partial mode)")
        else:
            eval_dataset = dataset_items

        run_eval_out = evaluate_model_run(eval_dataset, raw_records, seed=args.seed)
        m = run_eval_out["metrics"]
        ci = run_eval_out["ci_95"]

        all_models_results[model_name] = {
            "metrics": m,
            "ci_95": ci,
            "per_category": run_eval_out["per_category"],
            "confusion_matrix": run_eval_out["confusion_matrix"],
            "robustness": run_eval_out["robustness"],
        }

        # Save per-model confusion matrix and per-category stats
        model_dir = raw_path.parent
        model_dir.mkdir(parents=True, exist_ok=True)

        # Confusion CSV
        conf_file = model_dir / "confusion.csv"
        with open(conf_file, "w", encoding="utf-8") as cf:
            cf.write("gold_category,pred_answerable,pred_missing,pred_conflict,pred_ambiguous,pred_PARSE_FAIL,total\n")
            for r in run_eval_out["confusion_matrix"]:
                cf.write(f"{r['gold_category']},{r['pred_answerable']},{r['pred_missing']},{r['pred_conflict']},{r['pred_ambiguous']},{r['pred_PARSE_FAIL']},{r['total']}\n")

        # Per Category CSV
        cat_file = model_dir / "per_category.csv"
        with open(cat_file, "w", encoding="utf-8") as ctf:
            ctf.write("category,support,precision,recall,f1\n")
            for r in run_eval_out["per_category"]:
                ctf.write(f"{r['category']},{r['support']},{r['precision']},{r['recall']},{r['f1']}\n")

        # Per Company CSV
        comp_file = model_dir / "per_company.csv"
        with open(comp_file, "w", encoding="utf-8") as cpf:
            cpf.write("source_report,n,decision_accuracy,reason_macro_f1\n")
            for r in run_eval_out["robustness"]["per_company"]:
                cpf.write(f"{r['source_report']},{r['n']},{r['decision_accuracy']},{r['reason_macro_f1']}\n")

        # Print model summary
        print(f"  Reason Macro-F1:   {m['reason_macro_f1']:.3f} (95% CI: {ci['reason_macro_f1']})")
        print(f"  Decision Accuracy: {m['decision_accuracy']:.3f} (95% CI: {ci['decision_accuracy']})")
        print(f"  Over-refusal Rate: {m['over_refusal_rate']:.3f} (95% CI: {ci['over_refusal_rate']})")
        print(f"  Over-answer Rate:  {m['over_answer_rate']:.3f} (95% CI: {ci['over_answer_rate']})")
        print(f"  Answer EM:         {m['answer_em']:.3f} (95% CI: {ci['answer_em']})")
        print(f"  Answer Token-F1:   {m['answer_f1']:.3f} (95% CI: {ci['answer_f1']})")
        print(f"  Parse-fail Rate:   {m['parse_fail_rate']:.3f} (95% CI: {ci['parse_fail_rate']})")

        # Accumulate row for results.csv
        csv_rows.append({
            "model": model_name,
            "reason_macro_f1": round(m["reason_macro_f1"], 4),
            "macro_f1_ci_lo": ci["reason_macro_f1"][0],
            "macro_f1_ci_hi": ci["reason_macro_f1"][1],
            "decision_acc": round(m["decision_accuracy"], 4),
            "dec_acc_ci_lo": ci["decision_accuracy"][0],
            "dec_acc_ci_hi": ci["decision_accuracy"][1],
            "over_refusal": round(m["over_refusal_rate"], 4),
            "over_refusal_ci_lo": ci["over_refusal_rate"][0],
            "over_refusal_ci_hi": ci["over_refusal_rate"][1],
            "over_answer": round(m["over_answer_rate"], 4),
            "over_answer_ci_lo": ci["over_answer_rate"][0],
            "over_answer_ci_hi": ci["over_answer_rate"][1],
            "answer_f1": round(m["answer_f1"], 4),
            "answer_f1_ci_lo": ci["answer_f1"][0],
            "answer_f1_ci_hi": ci["answer_f1"][1],
            "parse_fail": round(m["parse_fail_rate"], 4),
            "parse_fail_ci_lo": ci["parse_fail_rate"][0],
            "parse_fail_ci_hi": ci["parse_fail_rate"][1],
        })

        # LaTeX row
        latex_rows.append(
            f"{model_name} & {format_ci(m['reason_macro_f1'], ci['reason_macro_f1'])} & "
            f"{format_ci(m['decision_accuracy'], ci['decision_accuracy'])} & "
            f"{format_ci(m['over_refusal_rate'], ci['over_refusal_rate'])} & "
            f"{format_ci(m['over_answer_rate'], ci['over_answer_rate'])} & "
            f"{format_ci(m['answer_f1'], ci['answer_f1'])} & "
            f"{format_ci(m['parse_fail_rate'], ci['parse_fail_rate'])} \\\\"
        )

    # Add Baselines to results.csv and table.tex
    for b_name, b_info in baselines.items():
        bm = b_info["metrics"]
        bci = b_info["ci_95"]
        display_name = b_name.replace("_", "-")
        csv_rows.append({
            "model": f"baseline-{display_name}",
            "reason_macro_f1": round(bm["reason_macro_f1"], 4),
            "macro_f1_ci_lo": bci["reason_macro_f1"][0],
            "macro_f1_ci_hi": bci["reason_macro_f1"][1],
            "decision_acc": round(bm["decision_accuracy"], 4),
            "dec_acc_ci_lo": bci["decision_accuracy"][0],
            "dec_acc_ci_hi": bci["decision_accuracy"][1],
            "over_refusal": round(bm["over_refusal_rate"], 4),
            "over_refusal_ci_lo": bci["over_refusal_rate"][0],
            "over_refusal_ci_hi": bci["over_refusal_rate"][1],
            "over_answer": round(bm["over_answer_rate"], 4),
            "over_answer_ci_lo": bci["over_answer_rate"][0],
            "over_answer_ci_hi": bci["over_answer_rate"][1],
            "answer_f1": round(bm["answer_f1"], 4),
            "answer_f1_ci_lo": bci["answer_f1"][0],
            "answer_f1_ci_hi": bci["answer_f1"][1],
            "parse_fail": round(bm["parse_fail_rate"], 4),
            "parse_fail_ci_lo": bci["parse_fail_rate"][0],
            "parse_fail_ci_hi": bci["parse_fail_rate"][1],
        })

        latex_rows.append(
            f"\\textit{{{display_name}}} & {format_ci(bm['reason_macro_f1'], bci['reason_macro_f1'])} & "
            f"{format_ci(bm['decision_accuracy'], bci['decision_accuracy'])} & "
            f"{format_ci(bm['over_refusal_rate'], bci['over_refusal_rate'])} & "
            f"{format_ci(bm['over_answer_rate'], bci['over_answer_rate'])} & "
            f"{format_ci(bm['answer_f1'], bci['answer_f1'])} & "
            f"{format_ci(bm['parse_fail_rate'], bci['parse_fail_rate'])} \\\\"
        )

    # 1. Output results.json
    results_json_data = {
        "models": all_models_results,
        "baselines": baselines,
        "dataset_items_count": len(dataset_items),
        "seed": args.seed,
    }
    with open(out_dir / "results.json", "w", encoding="utf-8") as jf:
        json.dump(results_json_data, jf, indent=2, ensure_ascii=False)

    # 2. Output results.csv
    header = [
        "model",
        "reason_macro_f1",
        "macro_f1_ci_lo",
        "macro_f1_ci_hi",
        "decision_acc",
        "dec_acc_ci_lo",
        "dec_acc_ci_hi",
        "over_refusal",
        "over_refusal_ci_lo",
        "over_refusal_ci_hi",
        "over_answer",
        "over_answer_ci_lo",
        "over_answer_ci_hi",
        "answer_f1",
        "answer_f1_ci_lo",
        "answer_f1_ci_hi",
        "parse_fail",
        "parse_fail_ci_lo",
        "parse_fail_ci_hi",
    ]
    with open(out_dir / "results.csv", "w", encoding="utf-8") as fcsv:
        fcsv.write(",".join(header) + "\n")
        for r in csv_rows:
            fcsv.write(",".join(str(r[k]) for k in header) + "\n")

    # 3. Output table.tex
    tex_content = [
        "\\begin{table*}[t]",
        "\\centering",
        "\\small",
        "\\begin{tabular}{lcccccc}",
        "\\toprule",
        "Model & Reason Macro-F1 & Decision Acc & Over-Refusal & Over-Answer & Answer F1 & Parse Fail \\\\",
        "\\midrule",
    ]
    tex_content.extend(latex_rows)
    tex_content.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\caption{FinAbstain Evaluation Results (Metrics reported as Value [95\\% Bootstrap CI]).}",
        "\\label{tab:finabstain_results}",
        "\\end{table*}",
    ])
    with open(out_dir / "table.tex", "w", encoding="utf-8") as ftex:
        ftex.write("\n".join(tex_content) + "\n")

    # Also save top-level confusion.csv, per_category.csv, per_company.csv if only 1 model
    if len(args.raw) == 1 and all_models_results:
        first_m = list(all_models_results.keys())[0]
        # Copy to out_dir if out_dir != model_dir
        if out_dir != Path(args.raw[0]).parent:
            with open(out_dir / "confusion.csv", "w", encoding="utf-8") as cf:
                cf.write("gold_category,pred_answerable,pred_missing,pred_conflict,pred_ambiguous,pred_PARSE_FAIL,total\n")
                for r in all_models_results[first_m]["confusion_matrix"]:
                    cf.write(f"{r['gold_category']},{r['pred_answerable']},{r['pred_missing']},{r['pred_conflict']},{r['pred_ambiguous']},{r['pred_PARSE_FAIL']},{r['total']}\n")
            with open(out_dir / "per_category.csv", "w", encoding="utf-8") as ctf:
                ctf.write("category,support,precision,recall,f1\n")
                for r in all_models_results[first_m]["per_category"]:
                    ctf.write(f"{r['category']},{r['support']},{r['precision']},{r['recall']},{r['f1']}\n")
            with open(out_dir / "per_company.csv", "w", encoding="utf-8") as cpf:
                cpf.write("source_report,n,decision_accuracy,reason_macro_f1\n")
                for r in all_models_results[first_m]["robustness"]["per_company"]:
                    cpf.write(f"{r['source_report']},{r['n']},{r['decision_accuracy']},{r['reason_macro_f1']}\n")

    print("\n" + "=" * 70)
    print("SCORING COMPLETE. OUTPUTS GENERATED:")
    print(f"  - {out_dir / 'results.json'}")
    print(f"  - {out_dir / 'results.csv'}")
    print(f"  - {out_dir / 'table.tex'}")
    print(f"  - {out_dir / 'confusion.csv'}")
    print(f"  - {out_dir / 'per_category.csv'}")
    print(f"  - {out_dir / 'per_company.csv'}")
    print("=" * 70)

if __name__ == "__main__":
    main()
