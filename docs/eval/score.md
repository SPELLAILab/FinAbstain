# `eval/score.py`

## Overview
[`eval/score.py`](file:///Users/kartiksirohi/FinAbstain/eval/score.py) is the comprehensive evaluation and scoring harness for FinAbstain. It parses model completions from `raw.jsonl`, compares model decisions and abstention reasons against gold benchmark labels, computes primary metrics, performs 1,000-sample bootstrap confidence intervals, computes standard baselines, and generates detailed breakdowns (confusion matrices, per-category statistics, and robustness subsets).

---

## How It Works

1. **Output Parsing**:
   - `parse_model_output`: Extracts JSON or markdown formatted key-value pairs (`decision`, `reason`, `answer`).
   - Consistency checking: Ensures that if `decision == "answer"`, then `reason == "none"`; and if `decision == "abstain"`, `reason` must be in `{missing, conflict, ambiguous}`.
   - Any malformed, unparseable, or inconsistent output is labeled `PARSE_FAIL` and scored as incorrect across all metrics.
2. **Metric Calculations**:
   - **Reason Macro-F1**: Unweighted average of F1 scores across the 4 categories (`answerable`, `missing`, `conflict`, `ambiguous`).
   - **Decision Accuracy**: Accuracy of binary classification (`answer` vs `abstain`).
   - **Over-refusal Rate**: Proportion of `answerable` items where the model refused to answer.
   - **Over-answer Rate**: Proportion of unanswerable items where the model attempted to answer.
   - **Answer Exact Match (EM) & Token-F1**: Evaluated on `answerable` items where the model chose to answer, utilizing numerical parsing ($1.2\text{M} = \$1,200,000$) and word-level F1.
   - **Parse-fail Rate**: Proportion of completions that failed JSON/formatting constraints.
3. **Statistical Confidence Intervals**: Computes 95% bootstrap confidence intervals ($B = 1000$) for all primary metrics using NumPy.
4. **Baselines**: Calculates performance metrics and 95% CIs for 3 deterministic baselines:
   - *Always Answer*: Answers every item.
   - *Always Abstain*: Abstains on every item with reason `missing`.
   - *Random Uniform*: Uniform random guessing across the 4 categories.
5. **Robustness Subsets**:
   - *Deterministic Only*: Evaluates performance exclusively on items that did not require LLM validation (`needs_llm_validation == False`).
   - *Per-Company Breakdown*: Stratifies metrics by source filing (e.g. `amzn`, `cat`, `pfe`, `ko`).
6. **Artifact Output**: Produces `results.json`, `results.csv`, `table.tex` (publication-ready LaTeX table), `confusion.csv`, and `per_category.csv`.

---

## Functions Reference

### `extract_balanced_json_objects(text: str) -> List[str]`
- **Purpose**: Locates all balanced `{...}` JSON blocks in completion text using depth-counting.
- **Parameters**: `text` (`str`).
- **Returns**: `List[str]`: List of JSON strings.

### `extract_first_balanced_json(text: str) -> Optional[str]`
- **Purpose**: Finds the most relevant JSON block, prioritizing blocks containing `"decision"`.
- **Parameters**: `text` (`str`).
- **Returns**: `Optional[str]`: Target JSON string or `None`.

### `normalize_text_for_answer(text: str) -> str`
- **Purpose**: Standardizes financial answers for exact matching (stripping `$`, commas, spaces, trailing periods, converting `(340)` to `-340`, and standardizing percentages).
- **Parameters**: `text` (`str`).
- **Returns**: `str`: Normalized text.

### `parse_numeric_val(text: str) -> Optional[float]`
- **Purpose**: Extracts floating-point values supporting magnitude multipliers (e.g., `"1.2 million"` $\to 1.2 \times 10^6$, `"3.5B"` $\to 3.5 \times 10^9$, `"12.5%"` $\to 12.5$).
- **Parameters**: `text` (`str`).
- **Returns**: `Optional[float]`: Parsed numeric float value.

### `compute_answer_em_and_f1(gold_answer: str, pred_answer: str, pred_decision: str) -> Tuple[float, float]`
- **Purpose**: Evaluates exact match and token overlap F1 score on answerable items.
- **Parameters**: `gold_answer` (`str`), `pred_answer` (`str`), `pred_decision` (`str`).
- **Returns**: `Tuple[float, float]`: `(em_score, f1_score)`.

### `parse_model_output(record: Dict[str, Any]) -> Tuple[str, str, str, bool]`
- **Purpose**: Parses model response from a raw evaluation record.
- **Parameters**: `record` (`Dict[str, Any]`): Entry from `raw.jsonl`.
- **Returns**: `Tuple[str, str, str, bool]`: `(decision, reason, answer, is_parse_fail)`.

### `compute_metrics_vectorized(gold_categories: List[str], pred_reasons: List[str], pred_decisions: List[str], gold_answers: List[str], pred_answers: List[str], is_parse_fails: List[bool], categories: List[str] = ALLOWED_CATEGORIES) -> Dict[str, float]`
- **Purpose**: Vectorized computation of all primary metrics.
- **Returns**: Dictionary with `reason_macro_f1`, `decision_accuracy`, `over_refusal_rate`, `over_answer_rate`, `answer_em`, `answer_f1`, `parse_fail_rate`.

### `bootstrap_confidence_intervals(gold_categories, pred_reasons, pred_decisions, gold_answers, pred_answers, is_parse_fails, seed=42, n_resamples=1000) -> Dict[str, Tuple[float, float]]`
- **Purpose**: Performs empirical bootstrap resampling to generate 95% confidence intervals `(2.5th, 97.5th percentiles)`.

### `compute_per_category_stats(gold_categories: List[str], pred_reasons: List[str]) -> List[Dict[str, Any]]`
- **Purpose**: Computes support, precision, recall, and F1 for each of the 4 benchmark categories.

### `compute_confusion_matrix(gold_categories: List[str], pred_reasons: List[str]) -> List[Dict[str, Any]]`
- **Purpose**: Generates a 4x5 confusion matrix (4 gold categories $\times$ 4 predicted categories + `PARSE_FAIL`).

### `compute_baselines(gold_categories: List[str], gold_answers: List[str], seed: int = 42) -> Dict[str, Dict[str, Any]]`
- **Purpose**: Computes metrics and 95% bootstrap CIs for `always_answer`, `always_abstain`, and `random_uniform` baselines.

### `evaluate_model_run(dataset_items: List[Dict[str, Any]], raw_records: List[Dict[str, Any]], seed: int = 42) -> Dict[str, Any]`
- **Purpose**: Coordinates full scoring logic for a single model run against benchmark dataset items.

### `format_ci(val: float, ci: Tuple[float, float], pct: bool = False) -> str`
- **Purpose**: Formats a score and its 95% confidence interval into a string representation: `0.725 [0.650, 0.795]`.

### `main() -> None`
- **Purpose**: CLI entrypoint. Supports scoring single or multiple model runs, comparing them against baselines, and outputting JSON, CSV, and LaTeX tables.

---

## Usage Example

```bash
# Score a single evaluated model run
python eval/score.py --data release/benchmark.jsonl --raw eval_out/granite-3.2-8b/raw.jsonl

# Compare multiple model runs
python eval/score.py --data release/benchmark.jsonl --raw eval_out/granite-3.2-8b/raw.jsonl eval_out/qwen-2.5-7b/raw.jsonl
```
