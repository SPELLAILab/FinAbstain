# Dataset Card for FinAbstain

## Dataset Summary
FinAbstain is a long-context financial reading comprehension and abstention benchmark. It evaluates whether an LLM can accurately determine when a question about a financial filing cannot be answered unambiguously, and if so, explain the exact rationale.

- **Total Items**: 143
- **Filing Sources**: 4 SEC FY2024 10-K Filings (Amazon, Caterpillar, Pfizer, Coca-Cola)
- **Context Length**: ~8,000 tokens padded long-context per item (with isolated single-section variants in `benchmark_short.jsonl`)
- **Categories**:
  - **ambiguous**: 22 items
  - **answerable**: 50 items
  - **conflict**: 38 items
  - **missing**: 33 items
- **Decision Distribution**:
  - **abstain**: 93 items
  - **answer**: 50 items
- **Source Breakdown**:
  - **Amazon.com, Inc. (FY2024)** (E-Commerce / Cloud): 17 items (`out/amzn/`)
  - **Caterpillar Inc. (FY2024)** (Industrial / Heavy Machinery): 32 items (`out/cat/`)
  - **Pfizer Inc. (FY2024)** (Pharmaceuticals / BioTech): 52 items (`out/pfe/`)
  - **The Coca-Cola Company (FY2024)** (Consumer Staples / Beverages): 42 items (`out/ko/`)

## Category Definitions
1. **answerable**: The context contains exactly one unambiguous answer.
2. **missing**: The context is on-topic, but the specific fact requested was omitted.
3. **conflict**: The context states two or more conflicting values for the exact same metric, period, and entity, without any reconciling explanation.
4. **ambiguous**: The question is underspecified along a key dimension (e.g. period, segment, unit), making multiple answers valid.

## Construction & Verification
- **Code-Applied Edits**: LLMs never rewrite whole passages; instead, they propose structured deletions or single-anchor insertions. The code deterministically applies and verifies diffs.
- **Dual Validation**: Items are validated by two independent frontier models (`gpt-oss:120b` and `nemotron-3-super`) under zero-shot blind instructions, requiring complete consensus with the gold category.
- **Leakage Guard**: Filler pool sections used for long-context padding are strictly filtered to ensure they do not introduce accidental answers or distractor resolution.

## Directory Structure
```
release/
├── benchmark.jsonl              # 143 items with 8,000-token padded contexts
├── benchmark_short.jsonl        # 143 items with isolated target sections (~400 tokens)
├── DATASET_CARD.md              # Documentation and taxonomy definitions
├── reports/
│   ├── raw/                     # Clean plain-text converted 10-K filings
│   │   ├── amzn.txt
│   │   ├── cat.txt
│   │   ├── pfe.txt
│   │   ├── ko.txt
│   └── anonymized/              # Anonymized & scaled text + entity mappings
│       ├── amzn.txt & amzn.mapping.json
│       ├── cat.txt & cat.mapping.json
│       ├── pfe.txt & pfe.mapping.json
│       ├── ko.txt & ko.mapping.json
├── run_manifest.json            # Pipeline execution metadata
└── stats.json                   # Aggregated generation & validation metrics
```

## Limitations
- Source texts originate from real SEC 10-K financial reports. While named entities and monetary values are scaled and anonymized, underlying tabular structure and industry phrasing may remain recognizable.

## License
MIT License.
