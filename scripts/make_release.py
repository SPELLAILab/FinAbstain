#!/usr/bin/env python3
"""Packages benchmark outputs into release/ folder with DATASET_CARD.md."""

import shutil
import json
from pathlib import Path
from collections import Counter

def make_release(out_dir_str: str = "out", release_dir_str: str = "release"):
    out_dir = Path(out_dir_str)
    release_dir = Path(release_dir_str)
    release_dir.mkdir(parents=True, exist_ok=True)

    bench_file = out_dir / "08_benchmark.jsonl"
    short_file = out_dir / "08_benchmark_short.jsonl"
    stats_file = out_dir / "stats.json"
    manifest_file = out_dir / "run_manifest.json"

    if not bench_file.exists():
        print(f"Error: {bench_file} not found. Run pipeline first.")
        return

    # Copy files
    shutil.copy(bench_file, release_dir / "benchmark.jsonl")
    if short_file.exists():
        shutil.copy(short_file, release_dir / "benchmark_short.jsonl")
    if stats_file.exists():
        shutil.copy(stats_file, release_dir / "stats.json")
    if manifest_file.exists():
        shutil.copy(manifest_file, release_dir / "run_manifest.json")

    # Analyze benchmark items
    items = []
    with open(bench_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    cat_counts = Counter(item.get("category") for item in items)
    dec_counts = Counter(item.get("gold_decision") for item in items)
    avg_tokens = sum(item.get("approx_tokens", 0) for item in items) / max(len(items), 1)

    dataset_card = f"""# Dataset Card for FinAbstain

## Dataset Summary
FinAbstain is a long-context financial reading comprehension and abstention benchmark. It evaluates whether an LLM can accurately determine when a question about a financial filing cannot be answered unambiguously, and if so, explain the exact rationale.

- **Total Items**: {len(items)}
- **Context Length**: ~{int(avg_tokens)} tokens average (padded)
- **Categories**:
{chr(10).join(f"  - **{cat}**: {count} items" for cat, count in sorted(cat_counts.items()))}
- **Decision Distribution**:
{chr(10).join(f"  - **{dec}**: {count}" for dec, count in sorted(dec_counts.items()))}

## Category Definitions
1. **answerable**: The context contains exactly one unambiguous answer.
2. **missing**: The context is on-topic, but the specific fact requested was omitted.
3. **conflict**: The context states two or more conflicting values for the exact same metric, period, and entity, without any reconciling explanation.
4. **ambiguous**: The question is underspecified along a key dimension (e.g. period, segment, unit), making multiple answers valid.

## Construction & Verification
- **Code-Applied Edits**: LLMs never rewrite whole passages; instead, they propose structured deletions or single-anchor insertions. The code deterministically applies and verifies diffs.
- **Dual Validation**: Items are validated by two independent frontier models (`gpt-oss:120b` and `nemotron-3-super`) under zero-shot blind instructions, requiring complete consensus with the gold category.
- **Leakage Guard**: Filler pool sections used for long-context padding are strictly filtered to ensure they do not introduce accidental answers or distractor resolution.

## Limitations
- Source texts originate from real SEC 10-K financial reports. While named entities and monetary values are scaled and anonymized, underlying tabular structure and industry phrasing may remain recognizable.

## License
MIT License.
"""
    (release_dir / "DATASET_CARD.md").write_text(dataset_card, encoding="utf-8")
    print(f"Successfully packaged {len(items)} items into '{release_dir}/'")

if __name__ == "__main__":
    make_release()
