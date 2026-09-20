# FinAbstain Evaluation Harness & PBS Runner

This folder contains the complete, self-contained evaluation and scoring suite for the FinAbstain benchmark. It is designed to be directly copied or uploaded to an H100 cluster node alongside `./release/`.

**Dependencies**: Standard Python 3.9+ library, `requests`, and `numpy` ONLY (compatible with air-gapped compute nodes).

---

## 📂 Directory Contents

```
eval/
├── run_eval.py               # Sends benchmark items to llama-server OpenAI endpoint
├── score.py                  # Computes Macro-F1, EM, CIs, baselines, and tables
├── prompts/
│   └── eval_prompt.txt       # Frozen zero-shot evaluation prompt template
├── run_eval.pbs              # PBS batch submission script with MIG GPU support
├── README.md                 # Usage documentation and cluster instructions
└── DECISIONS.md              # Technical and design decisions log
```

---

## ⚡ Quick Start: PBS Cluster Execution

### 1. Configure the Job Script
Open [`eval/run_eval.pbs`](file:///Users/kartiksirohi/financial-eval/eval/run_eval.pbs) and verify the variables at the top of the file:
```bash
MIG_UUID="MIG-2f219700-5dc6-59eb-81ef-2bb9414d3ec0"   # GPU 1 | H100 NVL | MIG 3g.47gb
MODEL_NAME="Qwen3.5-9B-Q8_0"                           # Model identifier label
LLAMA_SERVER="${HOME}/llama.cpp/build/bin/llama-server" # Path to llama-server binary
GGUF_PATTERN="${HOME}/.cache/.../*.gguf"               # Path or glob to your GGUF model file
```

### 2. Run Smoke Test First (8 Items)
Run an initial verification pass on 2 items per category to verify server readiness, prompt tokens, thinking suppression, and JSON parsing:
```bash
qsub -v SMOKE=1 eval/run_eval.pbs
```
Or run interactively:
```bash
SMOKE=1 ./eval/run_eval.pbs
```

### 3. Run Full Benchmark (143 Items)
Once the smoke test verifies 0 context overflows and clean JSON formatting:
```bash
qsub eval/run_eval.pbs
```

---

## 💻 Manual / Interactive Usage

### 1. Launch `llama-server`
```bash
CUDA_VISIBLE_DEVICES=0 ~/llama.cpp/build/bin/llama-server \
  -m /path/to/qwen3.5-9b-q8_0.gguf \
  -ngl 999 \
  -c 16384 \
  -np 1 \
  --jinja \
  --host 127.0.0.1 \
  --port 8080 \
  --chat-template-kwargs '{"enable_thinking":false}'
```

### 2. Run Evaluation (`run_eval.py`)

#### Smoke Test (8 items: 2 per category):
```bash
python eval/run_eval.py \
  --model-name "Qwen3.5-9B-Q8_0" \
  --base-url "http://127.0.0.1:8080" \
  --smoke
```

#### Full Evaluation Run (143 items):
```bash
python eval/run_eval.py \
  --data "release/benchmark.jsonl" \
  --model-name "Qwen3.5-9B-Q8_0" \
  --base-url "http://127.0.0.1:8080" \
  --out-dir "eval_out/Qwen3.5-9B-Q8_0" \
  --ctx 16384 \
  --max-tokens 200
```

#### Resuming an Interrupted Job
`run_eval.py` records items to `raw.jsonl` as they complete and automatically skips already-evaluated IDs on resubmission:
```bash
python eval/run_eval.py \
  --model-name "Qwen3.5-9B-Q8_0" \
  --base-url "http://127.0.0.1:8080"
```

---

### 3. Score Benchmark Run (`score.py`)

#### Score Single Model:
```bash
python eval/score.py \
  --data "release/benchmark.jsonl" \
  --raw "eval_out/Qwen3.5-9B-Q8_0/raw.jsonl" \
  --out-dir "eval_out/Qwen3.5-9B-Q8_0" \
  --seed 42
```

#### Score Multiple Models (Combined Leaderboard):
```bash
python eval/score.py \
  --data "release/benchmark.jsonl" \
  --raw eval_out/Qwen3.5-9B-Q8_0/raw.jsonl eval_out/Llama-3.1-8B-Q8_0/raw.jsonl \
  --out-dir "eval_out/combined" \
  --seed 42
```

---

## 📊 Output Artifacts Generated

In the output directory (e.g. `eval_out/Qwen3.5-9B-Q8_0/`):
- `raw.jsonl`: Line-by-line model completions, latency, token counts, and error status.
- `manifest.json`: Full provenance record (GGUF model name, server version, request settings, dataset SHA-256, prompt SHA-256, timestamps).
- `results.json`: Full JSON dictionary of all metrics, bootstrap confidence intervals, baseline evaluations, and robustness slices.
- `results.csv`: Flat table containing model performance alongside 95% bootstrap confidence intervals.
- `confusion.csv`: 4x4 confusion matrix across categories + explicit `pred_PARSE_FAIL` column.
- `per_category.csv`: Support, precision, recall, and F1 for each category (`answerable`, `missing`, `conflict`, `ambiguous`).
- `per_company.csv`: Performance breakdown by filing (`AMZN`, `CAT`, `PFE`, `KO`).
- `table.tex`: Formatted LaTeX table ready for direct paper inclusion:
  `Model & Reason Macro-F1 & Decision Acc & Over-Refusal & Over-Answer & Answer F1 & Parse Fail`
