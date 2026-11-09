# CHUOT Selective-Delegation Benchmark v1 (smoke stage)

This package is intentionally separate from `rat/engine`. The first milestone implements **B0 Local-only**: one Ollama generation per GSM8K task, no verifier-triggered repair, and no cloud calls.

## Current scope

- Dataset: official GSM8K `test` split.
- Smoke sample: deterministic 20-task sample (seed 42); task IDs and original row indices are retained.
- Local model: `qwen3:4b-instruct` by default, configurable without editing code.
- Evaluation: external numeric exact-match against the GSM8K answer after `####`.
- Output: one JSON object per task in JSONL, including latency, token counts, model, dataset checksum, and correctness.
- Cloud config defaults to Gemini `gemini-2.5-flash`, but B0 does not initialize or call any cloud provider.

The 20 examples are a pipeline smoke test only. Do not use this subset to tune prompts, policies, or report final benchmark performance. Freeze the complete protocol before running the full held-out test split.

## Setup (from repository root)

```bash
python -m pip install -r benchmarks/selective_delegation/requirements.txt
# Ensure Ollama is running and the configured model is installed.
ollama list
python -m benchmarks.selective_delegation.runner
```

Overrides:

```bash
python -m benchmarks.selective_delegation.runner --limit 20
python -m benchmarks.selective_delegation.runner --model qwen3:4b-instruct --output results/b0.jsonl
```

`--cloud-provider` is reserved for the cloud-enabled strategies and has no effect on B0. Cloud provider selection is deliberately not wired into the local-only path.

## Output and interpretation

Each JSONL row stores the original question, normalized ground truth, full model response, parsed numeric prediction, correctness, latency, token usage, provider/model ID, dataset SHA-256, and run metadata. A missing parse counts as incorrect. Token usage is marked unknown if Ollama does not report it.

Do not treat `verification_status: NOT_RUN` as a verifier pass. GSM8K answer matching is an external evaluator, not CHUOT's internal verifier. Arithmetic answer matching does not prove that a general verifier understood the word problem.

## Planned extensions

1. Shared cloud-client protocol and provider factory (Gemini first; Anthropic can be added without changing strategy interfaces).
2. B1-B4 baselines and B5 selective policy.
3. Repeated runs, confidence intervals, paired statistics, and cost/accuracy Pareto analysis.
