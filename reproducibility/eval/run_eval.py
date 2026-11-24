#!/usr/bin/env python3
"""
FinAbstain Evaluation Runner: runs benchmark items against a llama-server (OpenAI-compatible) endpoint.
Sequential execution, timeout handling, retries, resume support, context overflow checks, and manifest logging.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

import requests

ALLOWED_CATEGORIES = {"answerable", "missing", "conflict", "ambiguous"}
ALLOWED_GOLD_DECISIONS = {"answer", "abstain"}
ALLOWED_GOLD_REASONS = {"none", "missing", "conflict", "ambiguous"}

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def validate_dataset_schema(filepath: Path) -> Tuple[List[Dict[str, Any]], str]:
    if not filepath.exists():
        raise FileNotFoundError(f"Dataset file not found: {filepath}")

    sha256_hash = compute_sha256(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()
        if not first_line.strip():
            raise ValueError(f"Dataset file is empty: {filepath}")
        line1 = json.loads(first_line)

    # Required fields per spec
    required_keys = [
        "id",
        "category",
        "gold_decision",
        "gold_reason",
        "question",
        "gold_answer",
        "context",
        "needs_llm_validation",
    ]

    missing_keys = [k for k in required_keys if k not in line1]
    if "source_report" not in line1 and "report_id" not in line1:
        missing_keys.append("source_report (or report_id)")

    if missing_keys:
        raise ValueError(
            f"Dataset schema error in {filepath}: Line 1 missing required fields: {missing_keys}"
        )

    # Validate value constraints on line 1
    if line1["category"] not in ALLOWED_CATEGORIES:
        raise ValueError(f"Invalid category on line 1: {line1['category']}")
    if line1["gold_decision"] not in ALLOWED_GOLD_DECISIONS:
        raise ValueError(f"Invalid gold_decision on line 1: {line1['gold_decision']}")
    if line1["gold_reason"] not in ALLOWED_GOLD_REASONS:
        raise ValueError(f"Invalid gold_reason on line 1: {line1['gold_reason']}")

    # Read all items and normalize source_report
    items = []
    with open(filepath, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if "source_report" not in item:
                item["source_report"] = item.get("report_id", "unknown")
            items.append(item)

    return items, sha256_hash

def query_server_metadata(base_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Attempts to query /props or /v1/models to get GGUF filename and server info."""
    gguf_name = None
    server_ver = None
    clean_url = base_url.rstrip("/")

    # Try /props
    try:
        r = requests.get(f"{clean_url}/props", timeout=5)
        if r.status_code == 200:
            data = r.json()
            gguf_name = data.get("default_generation_settings", {}).get("model") or data.get("model_path")
            server_ver = data.get("version") or str(data.get("build", ""))
    except Exception:
        pass

    # Try /v1/models if gguf_name is still None
    if not gguf_name:
        try:
            r = requests.get(f"{clean_url}/v1/models", timeout=5)
            if r.status_code == 200:
                data = r.json()
                models_list = data.get("data", [])
                if models_list and isinstance(models_list, list):
                    gguf_name = models_list[0].get("id")
        except Exception:
            pass

    return gguf_name, server_ver

def strip_thinking(raw_text: str) -> Tuple[str, bool]:
    """Strips <think>...</think> blocks from output and flags whether thinking occurred."""
    if not raw_text:
        return "", False
    
    think_appeared = bool(
        "<think>" in raw_text or "</think>" in raw_text or re.search(r"<think>.*?</think>", raw_text, re.DOTALL)
    )
    
    # Strip complete think blocks
    clean = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
    # Strip unclosed think tag
    if "<think>" in clean:
        clean = re.sub(r"<think>.*", "", clean, flags=re.DOTALL)
    clean = clean.strip()
    return clean, think_appeared

def main():
    parser = argparse.ArgumentParser(description="FinAbstain Evaluation Harness Runner")
    parser.add_argument("--data", default="release/benchmark.jsonl", help="Path to benchmark JSONL")
    parser.add_argument("--model-name", required=True, help="Model label for reporting/paths")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="llama-server base URL")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: eval_out/<model-name>)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to evaluate")
    parser.add_argument("--smoke", action="store_true", help="Smoke test mode: 2 items per category = 8 items")
    parser.add_argument("--ctx", type=int, default=16384, help="Server context length for overflow assertions")
    parser.add_argument("--max-tokens", type=int, default=200, help="Maximum generation tokens per request")
    parser.add_argument("--prompt-file", default="eval/prompts/eval_prompt.txt", help="Path to evaluation prompt template")

    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(f"eval_out/{args.model_name}")
    out_dir.mkdir(parents=True, exist_ok=True)

    data_path = Path(args.data)
    prompt_path = Path(args.prompt_file)

    # 1. Inspect and validate dataset schema
    print("=" * 70)
    print(f"FINABSTAIN EVALUATION: {args.model_name}")
    print("=" * 70)
    print(f"Dataset path:       {data_path}")
    items, dataset_sha256 = validate_dataset_schema(data_path)
    print(f"Dataset SHA-256:    {dataset_sha256}")
    print(f"Total dataset size: {len(items)} items")

    # Load prompt template
    if not prompt_path.exists():
        # Fallback to local eval/prompts/eval_prompt.txt or relative
        alt_path = Path(__file__).parent / "prompts" / "eval_prompt.txt"
        if alt_path.exists():
            prompt_path = alt_path
        else:
            raise FileNotFoundError(f"Prompt template file not found: {prompt_path}")

    prompt_template = prompt_path.read_text(encoding="utf-8")
    prompt_sha256 = compute_sha256(prompt_path)
    print(f"Prompt template:    {prompt_path} (SHA-256: {prompt_sha256})")
    print(f"Target Server URL:  {args.base_url}")
    print(f"Output directory:   {out_dir}")
    print(f"Context length:     {args.ctx}")
    print(f"Max tokens:         {args.max_tokens}")

    # 2. Filter items if smoke test or limit
    if args.smoke:
        print("\n[SMOKE TEST MODE ENABLED: 2 items per category = 8 items total]")
        by_cat: Dict[str, List[Dict[str, Any]]] = {c: [] for c in ALLOWED_CATEGORIES}
        for it in items:
            cat = it["category"]
            if len(by_cat[cat]) < 2:
                by_cat[cat].append(it)
        smoke_items = []
        for cat in sorted(ALLOWED_CATEGORIES):
            smoke_items.extend(by_cat[cat])
        eval_items = smoke_items
        print(f"Selected {len(eval_items)} smoke test items.")
    elif args.limit is not None:
        eval_items = items[:args.limit]
        print(f"[LIMIT APPLIED: Evaluating first {len(eval_items)} items]")
    else:
        eval_items = items

    # 3. Check for existing results (RESUME capability)
    raw_file = out_dir / "raw.jsonl"
    completed_ids: Set[str] = set()
    if raw_file.exists():
        with open(raw_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        if "id" in record and record.get("id"):
                            completed_ids.add(record["id"])
                    except json.JSONDecodeError:
                        pass
        print(f"Resuming run: found {len(completed_ids)} already completed items in {raw_file}")

    # 4. Query server metadata
    gguf_name, server_ver = query_server_metadata(args.base_url)

    request_params = {
        "temperature": 0,
        "seed": 42,
        "max_tokens": args.max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "ctx": args.ctx,
    }

    start_iso = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    max_prompt_tokens_seen = 0
    context_overflow_count = 0
    processed_this_run = 0
    total_eval_items = len(eval_items)

    smoke_records = []

    clean_base_url = args.base_url.rstrip("/")
    chat_endpoint = f"{clean_base_url}/v1/chat/completions"

    with open(raw_file, "a", encoding="utf-8") as raw_out:
        for idx, item in enumerate(eval_items, 1):
            item_id = item["id"]
            if item_id in completed_ids:
                continue

            q = item["question"]
            ctx = item["context"]
            prompt_content = prompt_template.replace("{context}", ctx).replace("{question}", q)

            payload = {
                "messages": [{"role": "user", "content": prompt_content}],
                "temperature": 0,
                "seed": 42,
                "max_tokens": args.max_tokens,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            }

            t0 = time.time()
            res_text = ""
            err_msg = None
            prompt_tokens = 0
            completion_tokens = 0
            finish_reason = None
            think_stripped = False

            # Sequential requests with 2 retries on connection error
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    resp = requests.post(chat_endpoint, json=payload, timeout=300)
                    if resp.status_code == 200:
                        data = resp.json()
                        usage = data.get("usage", {})
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                        choices = data.get("choices", [])
                        if choices:
                            c0 = choices[0]
                            raw_content = c0.get("message", {}).get("content", "")
                            finish_reason = c0.get("finish_reason")
                            res_text, think_stripped = strip_thinking(raw_content)
                        break
                    else:
                        # Server returned error response (e.g. 400 context overflow)
                        err_body = resp.text
                        if any(kw in err_body.lower() for kw in ["context", "overflow", "token limit", "exceed"]):
                            err_msg = "context_overflow"
                            finish_reason = "context_overflow"
                        else:
                            err_msg = f"HTTP_{resp.status_code}: {err_body[:200]}"
                        if resp.status_code >= 500 and attempt < max_retries:
                            time.sleep(2 * (attempt + 1))
                            continue
                        break
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ex:
                    if attempt < max_retries:
                        time.sleep(2 * (attempt + 1))
                        continue
                    err_msg = f"ConnectionError: {str(ex)}"
                except Exception as ex:
                    err_msg = f"Exception: {str(ex)}"
                    break

            latency_s = round(time.time() - t0, 3)

            # Context overflow check
            if (prompt_tokens + completion_tokens > args.ctx) or (err_msg == "context_overflow"):
                err_msg = "context_overflow"
                context_overflow_count += 1

            if prompt_tokens > max_prompt_tokens_seen:
                max_prompt_tokens_seen = prompt_tokens

            out_record = {
                "id": item_id,
                "raw_text": res_text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "finish_reason": finish_reason,
                "latency_s": latency_s,
                "think_stripped": think_stripped,
                "error": err_msg,
            }

            raw_out.write(json.dumps(out_record, ensure_ascii=False) + "\n")
            raw_out.flush()

            completed_ids.add(item_id)
            processed_this_run += 1

            if args.smoke:
                smoke_records.append((item, out_record))

            # Progress logging every 10 items or on completion
            current_done = len(completed_ids)
            if (processed_this_run % 10 == 0) or (current_done == total_eval_items):
                elapsed = time.time() - start_time
                avg_time = elapsed / max(processed_this_run, 1)
                remaining = total_eval_items - current_done
                eta_s = remaining * avg_time
                print(
                    f"[Progress] {current_done}/{total_eval_items} items ({(current_done/total_eval_items)*100:.1f}%) | "
                    f"Last Latency: {latency_s}s | Elapsed: {elapsed:.1f}s | ETA: {eta_s:.1f}s"
                )

    end_iso = datetime.now(timezone.utc).isoformat()

    # 5. Write manifest.json
    manifest = {
        "model_name": args.model_name,
        "gguf_filename": gguf_name,
        "server_version": server_ver,
        "base_url": args.base_url,
        "request_params": request_params,
        "dataset_path": str(data_path),
        "dataset_sha256": dataset_sha256,
        "prompt_file_path": str(prompt_path),
        "prompt_file_sha256": prompt_sha256,
        "python_version": sys.version,
        "package_versions": {
            "requests": requests.__version__,
        },
        "start_time": start_iso,
        "end_time": end_iso,
        "total_items_in_dataset": len(items),
        "evaluated_items_count": len(completed_ids),
        "max_prompt_tokens": max_prompt_tokens_seen,
        "context_overflow_count": context_overflow_count,
        "smoke_mode": args.smoke,
    }

    manifest_file = out_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("EVALUATION RUN COMPLETE")
    print("=" * 70)
    print(f"Results file:           {raw_file}")
    print(f"Manifest file:          {manifest_file}")
    print(f"Total evaluated items:  {len(completed_ids)}")
    print(f"Max prompt tokens seen: {max_prompt_tokens_seen} / {args.ctx}")
    print(f"Context overflow items: {context_overflow_count} (Must be 0 for full run)")

    # Smoke test reporting requirements
    if args.smoke:
        print("\n" + "=" * 70)
        print("SMOKE TEST RESULTS REPORT (8 ITEMS)")
        print("=" * 70)
        by_category_samples = {}
        for item, rec in smoke_records:
            cat = item["category"]
            # Quick parse check
            parse_ok = False
            try:
                m_json = re.search(r"\{.*?\}", rec["raw_text"], re.DOTALL)
                if m_json:
                    p = json.loads(m_json.group(0))
                    if "decision" in p and "reason" in p:
                        parse_ok = True
            except Exception:
                pass

            print(
                f"- Item {rec['id']} [{cat.ljust(10)}] | Prompt tokens: {rec['prompt_tokens']} | "
                f"<think> appeared: {rec['think_stripped']} | Parse OK: {parse_ok} | Latency: {rec['latency_s']}s"
            )

            if cat not in by_category_samples:
                by_category_samples[cat] = (item, rec)

        print("\nExample Raw Output Per Category:")
        for cat, (item, rec) in by_category_samples.items():
            print(f"\n[{cat.upper()}] (Question: {item['question']})")
            print(f"Raw response:\n{rec['raw_text']}")
            if rec["error"]:
                print(f"Error: {rec['error']}")
        print("=" * 70)

if __name__ == "__main__":
    main()
