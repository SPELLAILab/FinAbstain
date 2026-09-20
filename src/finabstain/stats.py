from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

try:
    from sklearn.metrics import cohen_kappa_score, confusion_matrix
except ImportError:
    cohen_kappa_score = None
    confusion_matrix = None

class StatsTracker:
    def __init__(self):
        self.rejections: List[Dict[str, Any]] = []
        self.stage_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.llm_calls: int = 0
        self.cache_hits: int = 0

    def record_rejection(self, item_id: str, stage: str, reason: str, details: Optional[Dict[str, Any]] = None):
        entry = {
            "item_id": item_id,
            "stage": stage,
            "reason": reason,
        }
        if details:
            entry["details"] = details
        self.rejections.append(entry)
        self.stage_counts[stage]["rejected"] += 1

    def record_pass(self, stage: str):
        self.stage_counts[stage]["passed"] += 1

    def compute_validation_stats(self, validated_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes Cohen's kappa, agreement rate, and per-validator accuracy.
        """
        if not validated_items:
            return {}

        categories = ["answerable", "missing", "conflict", "ambiguous"]
        golds = []
        preds_a = []
        preds_b = []

        for item in validated_items:
            gold = item.get("category")
            val_a = item.get("validator_a", {}).get("label")
            val_b = item.get("validator_b", {}).get("label")
            if gold and val_a and val_b:
                golds.append(gold)
                preds_a.append(val_a)
                preds_b.append(val_b)

        n = len(golds)
        if n == 0:
            return {}

        acc_a = sum(1 for g, p in zip(golds, preds_a) if g == p) / n
        acc_b = sum(1 for g, p in zip(golds, preds_b) if g == p) / n
        agreement = sum(1 for a, b in zip(preds_a, preds_b) if a == b) / n
        both_correct = sum(1 for g, a, b in zip(golds, preds_a, preds_b) if g == a == b) / n

        kappa = None
        if cohen_kappa_score is not None:
            try:
                kappa = float(cohen_kappa_score(preds_a, preds_b, labels=categories))
            except Exception:
                kappa = None

        # Per category accuracy
        per_cat = {}
        for cat in categories:
            cat_indices = [i for i, g in enumerate(golds) if g == cat]
            cat_n = len(cat_indices)
            if cat_n > 0:
                cat_a = sum(1 for i in cat_indices if preds_a[i] == cat) / cat_n
                cat_b = sum(1 for i in cat_indices if preds_b[i] == cat) / cat_n
                cat_both = sum(1 for i in cat_indices if preds_a[i] == preds_b[i] == cat) / cat_n
                per_cat[cat] = {
                    "total": cat_n,
                    "accuracy_val_a": cat_a,
                    "accuracy_val_b": cat_b,
                    "both_correct_rate": cat_both,
                }

        return {
            "total_evaluated": n,
            "val_a_accuracy": acc_a,
            "val_b_accuracy": acc_b,
            "inter_annotator_agreement": agreement,
            "both_correct_rate": both_correct,
            "cohen_kappa": kappa,
            "per_category": per_cat,
        }

    def save(self, path: str | Path, extra: Optional[Dict[str, Any]] = None):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "stage_counts": dict(self.stage_counts),
            "rejections": self.rejections,
            "llm_calls": self.llm_calls,
            "cache_hits": self.cache_hits,
        }
        if extra:
            data.update(extra)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
