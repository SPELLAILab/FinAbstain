# `pipeline.py`

## Overview
[`pipeline.py`](file:///Users/kartiksirohi/FinAbstain/pipeline.py) is the central CLI entrypoint for the FinAbstain benchmark generation pipeline. It coordinates the execution of stages 1 through 9 sequentially, routes input and output directories (including support for isolated per-report runs), initializes the shared LLM client with persistent disk caching, and records run statistics and execution metadata.

---

## How It Works

1. **CLI Argument Parsing**: Parses command-line flags such as `--config`, `--from-stage`, `--to-stage`, `--report`, `--candidates-per-category`, `--final-per-category`, `--fake-company-name`, `--force`, `--limit`, `--smoke`, and `--dry-run`.
2. **Configuration Loading**: Loads YAML settings into an [`AppConfig`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/config.py#L55-L118) object and applies any command-line overrides (such as company-specific directory routing or smoke-test constraints).
3. **LLM Client Initialization**: Instantiates [`LLMClient`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/llm.py#L65-L388), discovering model tags on the configured Ollama host or local endpoint, and sets up the SHA-256 disk cache directory.
4. **Smoke-Test Pre-Flight Connectivity**: If running in smoke test mode with a non-mock backend, verifies that each configured model role (`generator`, `validator_a`, `validator_b`) can successfully return valid JSON.
5. **Stage Execution (1 through 9)**:
   - **Stage 01: Anonymize** (`s01_anonymize.run_stage`)
   - **Stage 02: Chunk** (`s02_chunk.run_stage`)
   - **Stage 03: Assign** (`s03_assign.run_stage`)
   - **Stage 04: QGen** (`s04_qgen.run_stage`)
   - **Stage 05: Edit** (`s05_edit.run_stage`)
   - **Stage 06: Checks** (`s06_checks.run_stage`)
   - **Stage 07: Validate** (`s07_validate.run_stage`)
   - **Stage 08: Build** (`s08_build.run_stage`)
   - **Stage 09: Audit** (`s09_audit.run_stage`)
6. **Telemetry & Manifest Serialization**: Records overall runtime, git commit hash, configuration SHA-256 hash, resolved model mappings, total LLM calls, and cache hits into `run_manifest.json` and `stats.json`.

---

## Functions Reference

### `get_git_commit() -> str`
- **Purpose**: Retrieves the current git commit SHA-1 of the working directory.
- **Parameters**: None.
- **Returns**: `str` representing the 40-character commit hash, or `"none"` if git execution fails.

### `run_smoke_test_checks(llm_client: LLMClient) -> None`
- **Purpose**: Executes a pre-flight connectivity check across all three required LLM model roles (`generator`, `validator_a`, `validator_b`).
- **Parameters**:
  - `llm_client` ([`LLMClient`](file:///Users/kartiksirohi/FinAbstain/src/finabstain/llm.py#L65-L388)): Initialized LLM client instance.
- **Behavior**: Sends a minimal prompt expecting JSON output `{"test": "ok", "number": 42}` to ensure network endpoints and model tags are functional before heavy execution starts.

### `main() -> None`
- **Purpose**: Main entrypoint orchestrating pipeline arguments, config loading, stage-by-stage loop execution, and manifest output.
- **Parameters**: None (reads from `sys.argv`).
- **Behavior**:
  - Sets up the `argparse.ArgumentParser`.
  - Supports `--dry-run` to calculate and display expected candidate items and estimated LLM call counts without making network requests.
  - Sequentially executes selected stages (within the `--from-stage` and `--to-stage` window).
  - Emits summary logs to stdout and saves `stats.json` and `run_manifest.json` to the target output directory.

---

## Usage Example

```bash
# Run full pipeline with default config
python pipeline.py --config config.yaml

# Run smoke test on a specific report
python pipeline.py --report cat --smoke

# Run stages 4 through 6 only, limiting to 5 candidates for debugging
python pipeline.py --from-stage 4 --to-stage 6 --limit 5
```
