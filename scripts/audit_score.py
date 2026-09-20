#!/usr/bin/env python3
"""Scores the human-filled audit.csv against gold categories.

Usage:
    python scripts/audit_score.py [path/to/audit.csv]
"""

import sys
import csv
from pathlib import Path
from collections import defaultdict

def score_audit(csv_path: Path):
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist.")
        sys.exit(1)

    total_rows = 0
    filled_rows = 0
    correct_count = 0
    per_category = defaultdict(lambda: {"total": 0, "correct": 0})
    disagreements = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            gold = str(row.get("category", "")).strip().lower()
            human = str(row.get("human_label", "")).strip().lower()
            notes = row.get("human_notes", "").strip()

            if not human:
                continue

            filled_rows += 1
            per_category[gold]["total"] += 1

            if human == gold:
                correct_count += 1
                per_category[gold]["correct"] += 1
            else:
                disagreements.append({
                    "id": row.get("id"),
                    "gold": gold,
                    "human": human,
                    "question": row.get("question"),
                    "notes": notes,
                })

    print("=" * 60)
    print("FINABSTAIN AUDIT SCORE REPORT")
    print("=" * 60)
    print(f"Total audit samples: {total_rows}")
    print(f"Human-annotated samples: {filled_rows} / {total_rows} ({filled_rows/max(total_rows, 1)*100:.1f}%)")

    if filled_rows == 0:
        print("\nNo rows have been labeled by a human yet. Fill 'human_label' column in audit.csv and rerun.")
        return

    overall_acc = correct_count / filled_rows
    print(f"\nOverall Human-Gold Agreement Accuracy: {overall_acc:.1%} ({correct_count}/{filled_rows})")

    print("\nPer-Category Breakdown:")
    print("-" * 50)
    for cat, counts in sorted(per_category.items()):
        tot = counts["total"]
        cor = counts["correct"]
        acc = cor / tot if tot > 0 else 0.0
        print(f"  {cat.ljust(15)}: {acc:.1%} ({cor}/{tot})")

    if disagreements:
        print("\nDisagreements:")
        print("-" * 50)
        for d in disagreements:
            print(f"  Item ID: {d['id']}")
            print(f"    Gold Label:  {d['gold']}")
            print(f"    Human Label: {d['human']}")
            print(f"    Question:    {d['question']}")
            if d['notes']:
                print(f"    Notes:       {d['notes']}")
            print()
    else:
        print("\nNo disagreements found! 100% agreement on annotated items.")

def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/audit.csv")
    score_audit(target)

if __name__ == "__main__":
    main()
