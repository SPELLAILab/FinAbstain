#!/usr/bin/env python3
"""FinAbstain Dataset Builder CLI Pipeline."""

import os
import sys
import argparse
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

from src.finabstain.config import AppConfig
from src.finabstain.llm import LLMClient
from src.finabstain.stats import StatsTracker
from src.finabstain.stages import (
    s01_anonymize,
    s02_chunk,
    s03_assign,
    s04_qgen,
    s05_edit,
    s06_checks,
    s07_validate,
    s08_build,
    s09_audit,
)

def get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "none"

def run_smoke_test_checks(llm_client: LLMClient):
    print("Running smoke test pre-flight connectivity and JSON checks...")
    test_messages = [{"role": "user", "content": 'Return ONLY JSON: {"test": "ok", "number": 42}'}]
    for role in ["generator", "validator_a", "validator_b"]:
        print(f"  Testing model role '{role}'...")
        raw, parsed, _ = llm_client.call_chat(role, test_messages, json_format=True)
        if not parsed or parsed.get("test") != "ok":
            print(f"Warning: Model {role} did not return expected JSON. Raw output: {(raw or '')[:100]}")
        else:
            print(f"  [OK] Model role '{role}' passed JSON smoke test.")

def main():
    parser = argparse.ArgumentParser(description="FinAbstain Dataset Builder")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--from-stage", type=int, default=1, choices=range(1, 10), help="Start from stage N (1-9)")
    parser.add_argument("--to-stage", type=int, default=9, choices=range(1, 10), help="Stop after stage M (1-9)")
    parser.add_argument("--report", default=None, help="Target specific report (e.g. cat, pfe, amzn)")
    parser.add_argument("--candidates-per-category", type=int, default=None, help="Override candidate items per category")
    parser.add_argument("--final-per-category", type=int, default=None, help="Override target benchmark items per category")
    parser.add_argument("--fake-company-name", default=None, help="Override fake company name for anonymization")
    parser.add_argument("--force", action="store_true", help="Recompute stages even if outputs exist")
    parser.add_argument("--limit", type=int, default=None, help="Process only K items per stage (debugging)")
    parser.add_argument("--smoke", action="store_true", help="Tiny end-to-end smoke test (1 item/category)")
    parser.add_argument("--dry-run", action="store_true", help="Print planned LLM calls without making any")

    args = parser.parse_args()

    # Load configuration
    cfg = AppConfig.load(args.config)

    # Handle per-report folder routing
    if args.report:
        report_clean = args.report.strip().rstrip("/")
        cfg.data.raw_dir = f"data/raw/{report_clean}"
        cfg.data.out_dir = f"out/{report_clean}"
        Path(cfg.data.out_dir).mkdir(parents=True, exist_ok=True)

    if args.candidates_per_category is not None:
        cfg.candidates_per_category = args.candidates_per_category
    if args.final_per_category is not None:
        cfg.final_per_category = args.final_per_category
    if args.fake_company_name:
        cfg.anonymize.fake_company_name = args.fake_company_name

    # Smoke test mode overrides
    if args.smoke:
        print("[Smoke Mode] Overriding config for fast verification (1 candidate per category).")
        cfg.candidates_per_category = 1
        cfg.final_per_category = 1
        cfg.audit.n_items = 4
        cfg.padding.target_tokens = [1000]

    cache_dir = Path(cfg.data.out_dir) / "cache"
    stats_tracker = StatsTracker()

    print(f"Starting FinAbstain Pipeline for [{args.report or 'all'}] (Seed: {cfg.seed}, Backend: {cfg.llm.backend})")
    print(f"  Input directory:  {cfg.data.raw_dir}")
    print(f"  Output directory: {cfg.data.out_dir}")

    if args.dry_run:
        print("\n--- DRY RUN SUMMARY ---")
        print(f"From stage: {args.from_stage} to stage: {args.to_stage}")
        print(f"Target items per category: {cfg.final_per_category}")
        print(f"Candidate items per category: {cfg.candidates_per_category}")
        print(f"Total planned candidates: {4 * cfg.candidates_per_category}")
        print(f"Estimated QGen LLM calls: {4 * cfg.candidates_per_category}")
        print(f"Estimated Edit LLM calls: {3 * cfg.candidates_per_category} (missing + conflict + ambiguous)")
        print(f"Estimated Validate LLM calls: 2 * (passed items)")
        print("Dry run complete. No network calls made.")
        return

    # Initialize LLM Client
    llm_client = LLMClient(cfg.llm, cache_dir=cache_dir, seed=cfg.seed)

    if args.smoke and cfg.llm.backend != "mock":
        run_smoke_test_checks(llm_client)

    start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Pipeline stages execution
    # Stage 01: Anonymize
    if args.from_stage <= 1 <= args.to_stage:
        print("\n=== Stage 01: Anonymize ===")
        s01_anonymize.run_stage(cfg, force=args.force)

    # Stage 02: Chunk
    if args.from_stage <= 2 <= args.to_stage:
        print("\n=== Stage 02: Chunk ===")
        s02_chunk.run_stage(cfg, force=args.force)

    # Stage 03: Assign
    if args.from_stage <= 3 <= args.to_stage:
        print("\n=== Stage 03: Assign ===")
        s03_assign.run_stage(cfg, force=args.force)

    # Stage 04: QGen
    if args.from_stage <= 4 <= args.to_stage:
        print("\n=== Stage 04: QGen ===")
        s04_qgen.run_stage(cfg, llm_client, stats_tracker, force=args.force, limit=args.limit)

    # Stage 05: Edit
    if args.from_stage <= 5 <= args.to_stage:
        print("\n=== Stage 05: Edit ===")
        s05_edit.run_stage(cfg, llm_client, stats_tracker, force=args.force, limit=args.limit)

    # Stage 06: Checks
    if args.from_stage <= 6 <= args.to_stage:
        print("\n=== Stage 06: Checks ===")
        s06_checks.run_stage(cfg, stats_tracker, force=args.force)

    # Stage 07: Validate
    if args.from_stage <= 7 <= args.to_stage:
        print("\n=== Stage 07: Validate ===")
        s07_validate.run_stage(cfg, llm_client, stats_tracker, force=args.force, limit=args.limit)

    # Stage 08: Build
    if args.from_stage <= 8 <= args.to_stage:
        print("\n=== Stage 08: Build ===")
        s08_build.run_stage(cfg, force=args.force)

    # Stage 09: Audit
    if args.from_stage <= 9 <= args.to_stage:
        print("\n=== Stage 09: Audit ===")
        s09_audit.run_stage(cfg, force=args.force)

    end_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Save stats and run manifest
    out_dir = Path(cfg.data.out_dir)
    stats_file = out_dir / "stats.json"
    stats_tracker.save(stats_file)

    cfg_str = json.dumps(cfg.raw_dict, sort_keys=True)
    manifest = {
        "timestamp_start": start_time,
        "timestamp_end": end_time,
        "config_sha256": hashlib.sha256(cfg_str.encode("utf-8")).hexdigest(),
        "git_commit": get_git_commit(),
        "resolved_model_tags": llm_client.tag_mapping,
        "base_url": llm_client.base_url,
        "llm_calls": stats_tracker.llm_calls,
        "cache_hits": stats_tracker.cache_hits,
    }
    with open(out_dir / "run_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\nFinAbstain Pipeline finished successfully.")
    print(f"Artifacts and benchmark written to: {cfg.data.out_dir}/")

if __name__ == "__main__":
    main()
