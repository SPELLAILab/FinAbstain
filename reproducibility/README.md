# FinAbstain: Reproduction Package

This directory contains the self-contained evaluation suite, benchmark datasets, ground-truth corporate reports, model generation outputs, and scoring harness to reproduce all empirical experiments presented in:

> **FinAbstain: Do Small Open Language Models Know Why a Financial Question Cannot Be Answered?**

---

## 📂 Directory Structure

```
reproducibility/
├── README.md                 # Reproduction guide and execution instructions
├── requirements.txt          # Minimal Python dependencies (requests, numpy)
├── checksums.sha256          # SHA-256 integrity verification hashes
│
├── eval/                     # Evaluation harness & scoring scripts
│   ├── run_eval.py           # Sends benchmark items sequentially to llama-server
│   ├── score.py              # Computes Macro-F1, Acc, EM, bootstrap CIs, tables
│   ├── run_eval.pbs          # PBS batch job script for NVIDIA H100 execution
│   ├── start_server.pbs      # PBS script to launch llama-server background daemon
│   └── prompts/
│       └── eval_prompt.txt   # Frozen zero-shot evaluation prompt template
│
├── data/                     # Benchmark datasets
│   ├── benchmark.jsonl       # Full benchmark (143 items, ~8k tokens padded context)
│   └── benchmark_short.jsonl # Short context unpadded benchmark (143 items)
│
├── reports/                  # SEC 10-K Corporate Reports used in the benchmark
│   ├── raw/                  # Original FY2024 10-K filings
│   │   ├── amzn.txt          # Amazon.com, Inc. (FY2024 10-K)
│   │   ├── cat.txt           # Caterpillar Inc. (FY2024 10-K)
│   │   ├── ko.txt            # The Coca-Cola Company (FY2024 10-K)
│   │   └── pfe.txt           # Pfizer Inc. (FY2024 10-K)
│   └── anonymized/           # Perturbed/anonymized text and monetary mappings
│       ├── amzn.txt & amzn.mapping.json
│       ├── cat.txt  & cat.mapping.json
│       ├── ko.txt   & ko.mapping.json
│       └── pfe.txt  & pfe.mapping.json
│
├── model_outputs/            # Raw generation logs from evaluated models (Q8_0 on H100)
│   ├── Qwen3.5-9B-Q8_0/raw.jsonl
│   ├── Granite-4.1-8B-Q8_0/raw.jsonl
│   └── Phi-4-Q8_0/raw.jsonl
│
└── human_eval/               # Human evaluation study pack & audited records
    ├── annotator.xlsx        # 44 audited items with human judgment vs. gold labels
    └── annotation_pack/      # Guidelines and blinded annotator evaluation sheets
```

---

## ⚡ 1. Setup & Environment

Only Python 3.9+ with `requests` and `numpy` is required:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Verify integrity of benchmark files and reports:
```bash
shasum -c checksums.sha256
```

---

## 📊 2. Instant Reproduction of Paper Results (Tables 1 & 2)

You can immediately reproduce all paper tables, metrics, bootstrap confidence intervals, and confusion matrices using the raw model generation outputs:

```bash
# Score Qwen3.5-9B
python3 eval/score.py --data data/benchmark.jsonl --input-dir model_outputs/Qwen3.5-9B-Q8_0 --seed 42

# Score Granite-4.1-8B
python3 eval/score.py --data data/benchmark.jsonl --input-dir model_outputs/Granite-4.1-8B-Q8_0 --seed 42

# Score Phi-4 (14B)
python3 eval/score.py --data data/benchmark.jsonl --input-dir model_outputs/Phi-4-Q8_0 --seed 42
```

This generates:
- `results.json`: Full metrics, Macro-F1, Decision Accuracy, Over-answer, Over-refusal, Token F1.
- `confusion.csv`: $4 \times 4$ category confusion matrix.
- `per_category.csv`: Category-wise precision, recall, and F1.
- `table.tex`: LaTeX table formatted for paper inclusion.

---

## 🚀 3. Running Model Inference From Scratch

To re-run inference on local hardware or an H100 GPU node using `llama.cpp` (`v0.4.1`):

### Step 1: Launch `llama-server`
```bash
./llama-server \
  -m /path/to/model-Q8_0.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 16384 \
  -ngl 99 \
  --seed 42
```

### Step 2: Run Evaluation
```bash
python3 eval/run_eval.py \
  --data data/benchmark.jsonl \
  --model-name "Qwen3.5-9B-Q8_0" \
  --base-url "http://127.0.0.1:8080" \
  --prompt-file "eval/prompts/eval_prompt.txt" \
  --ctx 16384 \
  --max-tokens 200 \
  --out-dir "eval_out/Qwen3.5-9B-Q8_0"
```

*(Note: For Granite-4.1-8B and Phi-4, set `--max-tokens 2048`.)*

### Step 3: Run Batch PBS Job on H100 Cluster
If running under PBS Professional on an H100 cluster:
```bash
qsub -v MODEL_NAME="Qwen3.5-9B-Q8_0" eval/run_eval.pbs
```
