"""Headless smoke runner for CHUOT selective-delegation benchmark."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.selective_delegation.datasets.gsm8k import DEFAULT_URL, download_gsm8k, load_gsm8k
from benchmarks.selective_delegation.strategies.local_only import LocalOnlyStrategy

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "benchmarks/selective_delegation/config/v1.yaml"
DATA_PATH = ROOT / "data/gsm8k/test.jsonl"


def load_config(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required. Install it with: pip install PyYAML") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def numeric_equal(prediction: str | None, target: str) -> bool:
    if prediction is None:
        return False
    try:
        return abs(float(prediction.replace(",", "")) - float(target.replace(",", ""))) <= 1e-9
    except (TypeError, ValueError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CHUOT reasoning benchmark smoke test")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cloud-provider", choices=("gemini", "anthropic"), default=None,
                        help="Provider override reserved for cloud-enabled strategies; B0 never calls cloud.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    dataset_cfg, local_cfg, run_cfg = config["dataset"], config["local"], config["run"]
    limit = args.limit or run_cfg.get("limit") or dataset_cfg.get("sample_size", 20)
    if not DATA_PATH.exists():
        digest = download_gsm8k(DATA_PATH, dataset_cfg.get("source_url", DEFAULT_URL))
        print(f"Downloaded GSM8K test split sha256={digest}")
    else:
        digest = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    tasks = load_gsm8k(DATA_PATH, limit=limit, seed=int(dataset_cfg.get("seed", 42)))

    # Import lazily so dataset parsing and tests do not require the application runtime.
    from rat.engine.slm import SLMEngine
    model = args.model or os.environ.get("CHUOT_LOCAL_MODEL") or local_cfg["model"]
    base_url = local_cfg.get("base_url")
    client = SLMEngine(ollama_url=base_url, model=model)
    if not client.is_service_running():
        raise RuntimeError(f"Ollama is unreachable at {base_url}. Start Ollama before running B0.")
    installed = client.list_installed_models()
    if not any(name == model or name.startswith(model + ":") for name in installed):
        raise RuntimeError(f"Model {model!r} is not installed. Available: {installed}")

    strategy = LocalOnlyStrategy(client, max_tokens=int(local_cfg.get("max_tokens", 1024)),
                                 timeout=float(local_cfg.get("timeout_seconds", 180)))
    output = args.output or ROOT / run_cfg.get("output", "results/gsm8k_smoke_local.jsonl")
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    correct = 0
    with output.open("w", encoding="utf-8") as handle:
        for index, task in enumerate(tasks, start=1):
            result = strategy.run(task)
            is_correct = numeric_equal(result["predicted_numeric"], task["ground_truth"])
            correct += int(is_correct)
            record = {
                **task,
                **result,
                "strategy": strategy.name,
                "correct": is_correct,
                "run_id": "smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                "model_provider": "ollama",
                "model_version": model,
                "dataset_sha256": digest,
                "prompt_version": "gsm8k-b0-v1",
                "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            status = "OK" if is_correct else "MISS"
            print(f"[{index:02d}/{len(tasks):02d}] {task['task_id']} {status} "
                  f"latency={result['latency_seconds']:.1f}s")
    print(f"\nB0 result: {correct}/{len(tasks)} correct ({correct / len(tasks):.1%})")
    print(f"JSONL: {output}")
    print(f"Dataset SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
