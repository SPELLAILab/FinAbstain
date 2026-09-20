import os
import json
from pathlib import Path
import pytest
import yaml

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

def test_full_pipeline_mock(tmp_path):
    # Setup test directories
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    out_dir = tmp_path / "out"

    fixture_path = Path("tests/fixtures/mini_report.txt")
    fixture_content = fixture_path.read_text(encoding="utf-8")
    for i in range(4):
        (raw_dir / f"report_mini_{i}.txt").write_text(fixture_content, encoding="utf-8")

    cfg_dict = {
        "seed": 42,
        "data": {
            "raw_dir": str(raw_dir),
            "out_dir": str(out_dir),
        },
        "sections": {
            "min_words": 30,
            "max_words": 150,
            "min_numbers": 1,
        },
        "candidates_per_category": 1,
        "final_per_category": 1,
        "padding": {
            "target_tokens": [150],
            "position": "random",
        },
        "anonymize": {
            "scale_factor_range": [0.6, 1.4],
            "fake_company_name": "Aldervane Holdings",
        },
        "llm": {
            "backend": "mock",
            "base_url": "https://ollama.com",
            "workers": 1,
            "max_retries": 1,
            "backoff_seconds": [1],
            "models": {
                "generator": {"name": "gemma4:31b", "think": None, "num_predict": 1024},
                "validator_a": {"name": "gpt-oss:120b", "think": "low", "num_predict": 2048},
                "validator_b": {"name": "nemotron-3-super", "think": None, "num_predict": 2048},
            },
        },
        "checks": {
            "conflict_min_rel_diff": 0.05,
            "max_inserted_words": 60,
            "min_kept_ratio_missing": 0.50,
        },
        "audit": {
            "n_items": 4,
        },
    }

    cfg = AppConfig.from_dict(cfg_dict)
    stats = StatsTracker()
    llm = LLMClient(cfg.llm, cache_dir=out_dir / "cache", seed=cfg.seed)

    # Run Stages 1 to 9
    s01_anonymize.run_stage(cfg, force=True)
    assert (out_dir / "01_anonymized" / "report_mini_0.txt").exists()

    s02_chunk.run_stage(cfg, force=True)
    assert (out_dir / "02_sections.jsonl").exists()

    s03_assign.run_stage(cfg, force=True)
    assert (out_dir / "03_assigned.jsonl").exists()

    s04_qgen.run_stage(cfg, llm, stats, force=True)
    assert (out_dir / "04_qgen.jsonl").exists()

    s05_edit.run_stage(cfg, llm, stats, force=True)
    assert (out_dir / "05_edits.jsonl").exists()

    s06_checks.run_stage(cfg, stats, force=True)
    assert (out_dir / "06_checked.jsonl").exists()

    s07_validate.run_stage(cfg, llm, stats, force=True)
    assert (out_dir / "07_validated.jsonl").exists()

    s08_build.run_stage(cfg, force=True)
    assert (out_dir / "08_benchmark.jsonl").exists()
    assert (out_dir / "08_benchmark_short.jsonl").exists()

    s09_audit.run_stage(cfg, force=True)
    assert (out_dir / "audit.csv").exists()

    # Verify benchmark schema
    with open(out_dir / "08_benchmark.jsonl", "r", encoding="utf-8") as f:
        bench_lines = [json.loads(line) for line in f if line.strip()]

    assert len(bench_lines) > 0
    item = bench_lines[0]
    required_keys = [
        "id", "category", "gold_decision", "gold_reason", "question",
        "context", "gold_answer", "original_answer", "evidence_span",
        "fact_type", "report_id", "section_id", "target_position",
        "target_section_index", "approx_tokens", "edit", "short_value_flag",
        "needs_llm_validation", "validator_a", "validator_b"
    ]
    for k in required_keys:
        assert k in item, f"Missing key '{k}' in benchmark record"
