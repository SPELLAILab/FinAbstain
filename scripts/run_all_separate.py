#!/usr/bin/env python3
"""
Run FinAbstain pipeline on multiple financial reports separately.
Creates dedicated per-report output folders with their own questions and benchmark,
and produces a consolidated final report.
"""

import sys
import subprocess
import json
import shutil
from pathlib import Path
from collections import Counter

REPORTS = [
    {
        "id": "amzn",
        "name": "Amazon.com, Inc. (FY2024)",
        "sector": "E-Commerce / Cloud",
        "fake_name": "Aldervane Holdings",
        "candidates": 12,
        "final": 8,
    },
    {
        "id": "cat",
        "name": "Caterpillar Inc. (FY2024)",
        "sector": "Industrial / Heavy Machinery",
        "fake_name": "Vanguard Heavy Industries",
        "candidates": 20,
        "final": 15,
    },
    {
        "id": "pfe",
        "name": "Pfizer Inc. (FY2024)",
        "sector": "Pharmaceuticals / BioTech",
        "fake_name": "Aethelgard Therapeutics",
        "candidates": 25,
        "final": 20,
    },
    {
        "id": "ko",
        "name": "The Coca-Cola Company (FY2024)",
        "sector": "Consumer Staples / Beverages",
        "fake_name": "Apex Refreshment Brands",
        "candidates": 25,
        "final": 20,
    },
]

def run_cmd(cmd: list):
    print(f"\n>> Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def main():
    print("=" * 70)
    print("FINABSTAIN MULTI-REPORT PIPELINE EXECUTION")
    print("=" * 70)

    for rep in REPORTS:
        rep_id = rep["id"]
        bench_file = Path(f"out/{rep_id}/08_benchmark.jsonl")
        if bench_file.exists() and bench_file.stat().st_size > 0:
            print(f"\n[SKIP] Report {rep['name']} already completed -> {bench_file}")
            continue

        print(f"\n{'=' * 70}")
        print(f"PROCESSING REPORT: {rep['name']} -> out/{rep_id}/")
        print(f"{'=' * 70}")

        cmd = [
            sys.executable,
            "pipeline.py",
            "--config", "config.yaml",
            "--report", rep_id,
            "--candidates-per-category", str(rep["candidates"]),
            "--final-per-category", str(rep["final"]),
            "--fake-company-name", rep["fake_name"],
        ]
        run_cmd(cmd)

    # Consolidate results
    print("\n" + "=" * 70)
    print("CONSOLIDATING BENCHMARKS INTO out/combined/ AND release/")
    print("=" * 70)

    combined_dir = Path("out/combined")
    release_dir = Path("release")
    raw_reports_dir = release_dir / "reports" / "raw"
    anon_reports_dir = release_dir / "reports" / "anonymized"

    combined_dir.mkdir(parents=True, exist_ok=True)
    release_dir.mkdir(parents=True, exist_ok=True)
    raw_reports_dir.mkdir(parents=True, exist_ok=True)
    anon_reports_dir.mkdir(parents=True, exist_ok=True)

    all_bench_items = []
    all_short_items = []
    per_report_stats = {}

    for rep in REPORTS:
        rep_id = rep["id"]
        bench_file = Path(f"out/{rep_id}/08_benchmark.jsonl")
        short_file = Path(f"out/{rep_id}/08_benchmark_short.jsonl")

        rep_items = []
        if bench_file.exists():
            with open(bench_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rep_items.append(json.loads(line))

        rep_short = []
        if short_file.exists():
            with open(short_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rep_short.append(json.loads(line))

        all_bench_items.extend(rep_items)
        all_short_items.extend(rep_short)
        per_report_stats[rep_id] = {
            "name": rep["name"],
            "sector": rep.get("sector", "N/A"),
            "count": len(rep_items),
            "categories": dict(Counter(i.get("category") for i in rep_items)),
        }

        # Copy raw and anonymized reports to release/reports/
        raw_src = Path(f"data/raw/{rep_id}/{rep_id}.txt")
        if raw_src.exists():
            shutil.copy2(raw_src, raw_reports_dir / f"{rep_id}.txt")

        anon_src = Path(f"out/{rep_id}/01_anonymized/{rep_id}.txt")
        if anon_src.exists():
            shutil.copy2(anon_src, anon_reports_dir / f"{rep_id}.txt")

        mapping_src = Path(f"out/{rep_id}/01_anonymized/{rep_id}.mapping.json")
        if mapping_src.exists():
            shutil.copy2(mapping_src, anon_reports_dir / f"{rep_id}.mapping.json")

    # Sort stably by id
    all_bench_items = sorted(all_bench_items, key=lambda x: x.get("id", ""))
    all_short_items = sorted(all_short_items, key=lambda x: x.get("id", ""))

    # Write combined benchmark files
    with open(combined_dir / "benchmark.jsonl", "w", encoding="utf-8") as f:
        for item in all_bench_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(combined_dir / "benchmark_short.jsonl", "w", encoding="utf-8") as f:
        for item in all_short_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(release_dir / "benchmark.jsonl", "w", encoding="utf-8") as f:
        for item in all_bench_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(release_dir / "benchmark_short.jsonl", "w", encoding="utf-8") as f:
        for item in all_short_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Update DATASET_CARD.md
    cat_totals = Counter(i.get("category") for i in all_bench_items)
    dec_totals = Counter(i.get("gold_decision") for i in all_bench_items)

    lines_card = [
        "# Dataset Card for FinAbstain",
        "",
        "## Dataset Summary",
        "FinAbstain is a long-context financial reading comprehension and abstention benchmark. It evaluates whether an LLM can accurately determine when a question about a financial filing cannot be answered unambiguously, and if so, explain the exact rationale.",
        "",
        f"- **Total Items**: {len(all_bench_items)}",
        f"- **Filing Sources**: {len(REPORTS)} SEC FY2024 10-K Filings ({', '.join(r['name'].split()[0] for r in REPORTS)})",
        "- **Context Length**: ~8,000 tokens padded long-context per item (with isolated single-section variants in `benchmark_short.jsonl`)",
        "- **Categories**:",
    ]
    for cat, cnt in sorted(cat_totals.items()):
        lines_card.append(f"  - **{cat}**: {cnt} items")
    lines_card.append("- **Decision Distribution**:")
    for dec, cnt in sorted(dec_totals.items()):
        lines_card.append(f"  - **{dec}**: {cnt} items")
    lines_card.append("- **Source Breakdown**:")
    for rep_id, st in per_report_stats.items():
        lines_card.append(f"  - **{st['name']}** ({st['sector']}): {st['count']} items (`out/{rep_id}/`)")

    lines_card.extend([
        "",
        "## Category Definitions",
        "1. **answerable**: The context contains exactly one unambiguous answer.",
        "2. **missing**: The context is on-topic, but the specific fact requested was omitted.",
        "3. **conflict**: The context states two or more conflicting values for the exact same metric, period, and entity, without any reconciling explanation.",
        "4. **ambiguous**: The question is underspecified along a key dimension (e.g. period, segment, unit), making multiple answers valid.",
        "",
        "## Construction & Verification",
        "- **Code-Applied Edits**: LLMs never rewrite whole passages; instead, they propose structured deletions or single-anchor insertions. The code deterministically applies and verifies diffs.",
        "- **Dual Validation**: Items are validated by two independent frontier models (`gpt-oss:120b` and `nemotron-3-super`) under zero-shot blind instructions, requiring complete consensus with the gold category.",
        "- **Leakage Guard**: Filler pool sections used for long-context padding are strictly filtered to ensure they do not introduce accidental answers or distractor resolution.",
        "",
        "## Directory Structure",
        "```",
        "release/",
        f"├── benchmark.jsonl              # {len(all_bench_items)} items with 8,000-token padded contexts",
        f"├── benchmark_short.jsonl        # {len(all_short_items)} items with isolated target sections (~400 tokens)",
        "├── DATASET_CARD.md              # Documentation and taxonomy definitions",
        "├── reports/",
        "│   ├── raw/                     # Clean plain-text converted 10-K filings",
    ])
    for r in REPORTS:
        lines_card.append(f"│   │   ├── {r['id']}.txt")
    lines_card.append("│   └── anonymized/              # Anonymized & scaled text + entity mappings")
    for r in REPORTS:
        lines_card.append(f"│       ├── {r['id']}.txt & {r['id']}.mapping.json")
    lines_card.extend([
        "├── run_manifest.json            # Pipeline execution metadata",
        "└── stats.json                   # Aggregated generation & validation metrics",
        "```",
        "",
        "## Limitations",
        "- Source texts originate from real SEC 10-K financial reports. While named entities and monetary values are scaled and anonymized, underlying tabular structure and industry phrasing may remain recognizable.",
        "",
        "## License",
        "MIT License.",
    ])

    with open(release_dir / "DATASET_CARD.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines_card) + "\n")

    # Final Report
    print("\n" + "=" * 70)
    print("FINAL MULTI-REPORT BENCHMARK REPORT")
    print("=" * 70)
    print(f"Total Combined Items: {len(all_bench_items)}")

    print("\nTotal Category Distribution:")
    for cat, cnt in sorted(cat_totals.items()):
        print(f"  - {cat.ljust(15)}: {cnt}")

    print("\nPer-Report Breakdown:")
    for rep_id, st in per_report_stats.items():
        print(f"\n  [{rep_id.upper()}] {st['name']} ({st['sector']})")
        print(f"    Folder: out/{rep_id}/")
        print(f"    Total items: {st['count']}")
        for c, cnt in sorted(st["categories"].items()):
            print(f"      - {c}: {cnt}")

    print("\nBenchmark files generated:")
    for r in REPORTS:
        print(f"  - out/{r['id']}/08_benchmark.jsonl")
    print("  - out/combined/benchmark.jsonl")
    print("  - release/benchmark.jsonl")
    print("=" * 70)

if __name__ == "__main__":
    main()
