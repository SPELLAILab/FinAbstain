# FinAbstain: Do Small Open Language Models Know Why a Financial Question Cannot Be Answered?

[![Paper: AAAI 2027](https://img.shields.io/badge/Accepted-AAAI%202027%20Student%20Abstract-blue.svg)](https://aaai.org)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Official repository for the AAAI 2027 Student Abstract paper:**  
> *"FinAbstain: Do Small Open Language Models Know Why a Financial Question Cannot Be Answered?"*  
> **Authors:** Kartik Sirohi, Kumar Prateek, Dr. Simranjit Singh (NIT Jalandhar)

---

## 📌 Overview

Language models answering questions about financial filings may give unsupported answers when the text does not support a single unambiguous answer. Such behavior reduces reliability and motivates reliable abstention. 

**FinAbstain** is a benchmark of 143 questions from four FY2024 SEC 10-K filings (Amazon, Caterpillar, Coca-Cola, Pfizer). Each question carries an ~8,000-token context and one of four fine-grained labels:
- **`Answerable` (50 items):** The context states exactly one verified fact that unambiguously answers the question.
- **`Missing` (33 items):** The context discusses the topic, but the specific metric or fact requested is absent.
- **`Conflict` (38 items):** The context asserts two or more mutually contradictory values for the same fact (same metric, entity, period) without reconciliation.
- **`Ambiguous` (22 items):** The question omits key qualifying constraints (period, segment, unit, entity), allowing multiple valid answers.

The benchmark evaluates whether small open models (<20B parameters: **Qwen3.5-9B**, **Granite-4.1-8B**, and **Phi-4**) can distinguish answerable financial questions from those requiring abstention—and whether they know *why*.

---

## 🔬 Key Empirical Findings

1. **High Answerable Accuracy:** All three models answer **49 of 50** answerable questions (98.0% recall, 2.0% over-refusal).
2. **Severe Over-Answering:** The models answer **63% to 73%** of unanswerable questions instead of abstaining.
3. **Reason Blindspots:** Small open models identify missing evidence in 52% to 76% of cases, but recover at most **11%** of conflicting cases and **9%** of ambiguous cases under strict scoring.
4. **Human Performance Ceiling:** An independent human evaluation across 44 items demonstrates **79.55%** 4-class accuracy, Cohen's $\kappa = 0.7295$, **86.36%** binary accuracy, and a **0.0%** over-refusal rate.

---

## 📂 Repository Structure

```
FinAbstain/
├── README.md                      # Main repository documentation & quick start
├── config.yaml                    # Configuration for dataset generation & model endpoints
├── requirements.txt               # Environment dependencies
├── pipeline.py                    # End-to-end benchmark construction orchestrator
├── supplementary_material.tex     # Complete standalone Supplementary Material (LaTeX)
│
├── src/finabstain/                # Core library modules
│   ├── config.py                  # YAML and environment configuration loader
│   ├── diffing.py                 # Deterministic edit application & verification
│   ├── io_utils.py                # Safe JSONL/JSON readers and writers
│   ├── llm.py                     # Ollama / OpenAI API client wrapper
│   ├── textnorm.py                # Text normalization and entity masking utilities
│   ├── stats.py                   # Benchmark summary statistics calculator
│   └── stages/                    # 9-stage pipeline implementation
│       ├── s01_anonymize.py       # Entity masking and monetary scaling
│       ├── s02_chunk.py           # Paragraph & table chunking into 200-600 word sections
│       ├── s03_assign.py          # Category assignment & filler pool partition
│       ├── s04_qgen.py            # Question-answer generation via Gemma 4 31B
│       ├── s05_edit.py            # Controlled perturbation generation (Conflict, Missing, Ambiguous)
│       ├── s06_checks.py          # Rule-based diff checks & reconciliation guards
│       ├── s07_validate.py        # Independent multi-judge blind validation
│       ├── s08_build.py           # 8k-token context padding & leakage guards
│       └── s09_audit.py           # Stratified human audit pack generator
│
├── eval/                          # Model evaluation & scoring harness
│   ├── run_eval.py                # Evaluation runner for llama-server OpenAI endpoint
│   ├── score.py                   # Scoring script (Macro-F1, EM, bootstrap CIs, tables)
│   ├── run_eval.pbs               # PBS batch job script for NVIDIA H100 execution
│   ├── start_server.pbs           # Script to launch llama-server daemon
│   └── prompts/
│       └── eval_prompt.txt        # Frozen zero-shot evaluation prompt
│
├── reproducibility/               # Self-contained bundle for instant experiment reproduction
│   ├── README.md                  # Step-by-step reproduction guide
│   ├── requirements.txt           # Minimal dependencies (requests, numpy)
│   ├── checksums.sha256           # SHA-256 data verification hashes
│   ├── data/                      # Benchmark files (benchmark.jsonl, benchmark_short.jsonl)
│   ├── reports/                   # Raw & anonymized SEC 10-K filings (AMZN, CAT, KO, PFE)
│   ├── model_outputs/             # Raw generation logs from Qwen3.5-9B, Granite-4.1-8B, Phi-4
│   └── human_eval/                # Blind human evaluation spreadsheets and guidelines
│
├── release/                       # Official benchmark release artifacts
│   ├── benchmark.jsonl            # 143 items with full 8k-token padded context
│   ├── benchmark_short.jsonl      # 143 items with short unpadded context
│   ├── annotator.xlsx             # 44 audited items with human vs. gold labels
│   ├── DATASET_CARD.md            # Detailed HuggingFace-style dataset card
│   └── stats.json                 # Benchmark distribution statistics
│
├── figures/                       # Publication-ready 300 DPI figures
│   ├── fig1_category_distribution_donut.png
│   ├── fig2_fact_types_and_reports.png
│   ├── fig3_token_length_distributions.png
│   ├── fig4_target_position_depth.png
│   ├── fig5_dataset_paper_dashboard.png
│   └── fig6_validation_rejection_funnel.png
│
├── scripts/                       # Maintenance & formatting utilities
│   ├── audit_score.py             # Human audit scoring utility
│   ├── generate_paper_figures.py  # Generates all publication charts from data
│   ├── html_to_txt.py             # SEC 10-K HTML to structured text converter
│   └── make_release.py            # Bundles dataset files with SHA-256 hashes
│
└── tests/                         # Pytest test suite
```

---

## ⚡ Quick Start: Reproducing Results

You can reproduce the paper's main scoring tables and bootstrap confidence intervals directly using the provided model generation logs:

```bash
cd reproducibility

# 1. Install minimal requirements
pip install -r requirements.txt

# 2. Verify dataset checksums
shasum -c checksums.sha256

# 3. Score Qwen3.5-9B
python3 eval/score.py --data data/benchmark.jsonl --input-dir model_outputs/Qwen3.5-9B-Q8_0 --seed 42

# 4. Score Granite-4.1-8B
python3 eval/score.py --data data/benchmark.jsonl --input-dir model_outputs/Granite-4.1-8B-Q8_0 --seed 42

# 5. Score Phi-4 (14B)
python3 eval/score.py --data data/benchmark.jsonl --input-dir model_outputs/Phi-4-Q8_0 --seed 42
```

---

## 🛠️ Running the Pipeline From Scratch

### Prerequisites
- Python 3.10+
- Local [Ollama](https://ollama.com) daemon or an Ollama Cloud API key:

```bash
git clone https://github.com/SPELLAILab/FinAbstain.git
cd FinAbstain
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Execution
```bash
# Smoke test (fast verification pass)
python pipeline.py --config config.yaml --smoke

# Full end-to-end benchmark construction
python pipeline.py --config config.yaml
```

---

## 📚 Citation

If you find this work or benchmark useful, please cite our AAAI 2027 paper:

```bibtex
@inproceedings{sirohi2027finabstain,
  title     = {FinAbstain: Do Small Open Language Models Know Why a Financial Question Cannot Be Answered?},
  author    = {Sirohi, Kartik and Prateek, Kumar and Singh, Simranjit},
  booktitle = {Proceedings of the AAAI Conference on Artificial Intelligence (Student Abstract Program)},
  year      = {2027}
}
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE). Corporate 10-K filings are public documents sourced from the U.S. Securities and Exchange Commission (SEC).
