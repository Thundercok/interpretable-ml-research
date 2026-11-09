"""Headless benchmark runner for CHUOT selective-delegation strategies."""
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
from benchmarks.selective_delegation.clients.factory import get_cloud_client
from benchmarks.selective_delegation.evaluation.metrics import compute_benchmark_metrics
from benchmarks.selective_delegation.report import generate_markdown_report
from benchmarks.selective_delegation.strategies.local_only import LocalOnlyStrategy
from benchmarks.selective_delegation.strategies.local_retry import LocalRetryStrategy
from benchmarks.selective_delegation.strategies.verified_repair import VerifiedRepairStrategy
from benchmarks.selective_delegation.strategies.always_cloud import AlwaysCloudStrategy
from benchmarks.selective_delegation.strategies.static_escalation import StaticEscalationStrategy
from benchmarks.selective_delegation.strategies.selective import SelectiveStrategy
from benchmarks.selective_delegation.strategies.frugalgpt import FrugalGPTStrategy
from benchmarks.selective_delegation.strategies.automix import AutoMixStrategy
from benchmarks.selective_delegation.strategies.peer_review import LocalPeerReviewStrategy
from rat.engine.experience_bank import ExperienceBank

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


def build_strategy(
    strategy_id: str,
    local_client: Any,
    cloud_client: Any,
    local_cfg: dict[str, Any],
    cloud_cfg: dict[str, Any],
):
    strat = strategy_id.lower().replace("-", "_")
    l_max = int(local_cfg.get("max_tokens", 1024))
    l_timeout = float(local_cfg.get("timeout_seconds", 180))
    c_max = int(cloud_cfg.get("max_tokens", 2048))

    if strat in ("b0", "local_only"):
        return LocalOnlyStrategy(local_client, max_tokens=l_max, timeout=l_timeout)
    if strat in ("b1", "local_retry"):
        return LocalRetryStrategy(local_client, max_tokens=l_max, timeout=l_timeout)
    if strat in ("b2", "verified_repair"):
        return VerifiedRepairStrategy(local_client, max_tokens=l_max, timeout=l_timeout, max_repairs=2)
    if strat in ("b3", "always_cloud"):
        if cloud_client is None:
            raise RuntimeError("Cloud client is required for B3 (always_cloud). Provide API key.")
        return AlwaysCloudStrategy(cloud_client, max_tokens=c_max)
    if strat in ("b4", "static_escalation"):
        if cloud_client is None:
            raise RuntimeError("Cloud client is required for B4 (static_escalation). Provide API key.")
        return StaticEscalationStrategy(local_client, cloud_client, local_max_tokens=l_max, cloud_max_tokens=c_max, timeout=l_timeout)
    if strat in ("b5", "selective"):
        if cloud_client is None:
            raise RuntimeError("Cloud client is required for B5 (selective). Provide API key.")
        return SelectiveStrategy(local_client, cloud_client, local_max_tokens=l_max, cloud_max_tokens=c_max, timeout=l_timeout, max_repairs=2)
    if strat in ("frugalgpt", "p1", "frugal"):
        if cloud_client is None:
            raise RuntimeError("Cloud client is required for FrugalGPT. Provide API key.")
        return FrugalGPTStrategy(local_client, cloud_client, local_max_tokens=l_max, cloud_max_tokens=c_max, timeout=l_timeout)
    if strat in ("automix", "p2"):
        if cloud_client is None:
            raise RuntimeError("Cloud client is required for AutoMix. Provide API key.")
        return AutoMixStrategy(local_client, cloud_client, local_max_tokens=l_max, cloud_max_tokens=c_max, timeout=l_timeout)
    if strat in ("peer_review", "peer", "b6"):
        if cloud_client is None:
            raise RuntimeError("Cloud client is required for Peer Review. Provide API key.")
        bank = ExperienceBank(ROOT / "data/benchmark_experience_bank.db")
        return LocalPeerReviewStrategy(
            local_client,
            cloud_client,
            local_max_tokens=l_max,
            cloud_max_tokens=c_max,
            timeout=l_timeout,
            experience_bank=bank,
        )

    raise ValueError(f"Unknown strategy: {strategy_id}. Available: b0, b1, b2, b3, b4, b5, b6, frugalgpt, automix, peer_review, all")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CHUOT reasoning benchmark")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--strategy", default="b0", choices=("b0", "b1", "b2", "b3", "b4", "b5", "b6", "all",
                                                            "local_only", "local_retry", "verified_repair",
                                                            "always_cloud", "static_escalation", "selective",
                                                            "frugalgpt", "automix", "peer_review", "peer", "p1", "p2"))
    parser.add_argument("--cloud-provider", choices=("gemini", "anthropic"), default=None,
                        help="Provider override for cloud-enabled strategies.")
    parser.add_argument("--cloud-model", default=None, help="Cloud model override.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--model", default=None, help="Local Ollama model override.")
    args = parser.parse_args()

    config = load_config(args.config)
    dataset_cfg, local_cfg, cloud_cfg, run_cfg = config["dataset"], config["local"], config.get("cloud", {}), config["run"]
    limit = args.limit or run_cfg.get("limit") or dataset_cfg.get("sample_size", 20)

    if not DATA_PATH.exists():
        digest = download_gsm8k(DATA_PATH, dataset_cfg.get("source_url", DEFAULT_URL))
        print(f"Downloaded GSM8K test split sha256={digest}")
    else:
        digest = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()

    tasks = load_gsm8k(DATA_PATH, limit=limit, seed=int(dataset_cfg.get("seed", 42)))

    # Local Ollama client
    from rat.engine.slm import SLMEngine
    local_model = args.model or os.environ.get("CHUOT_LOCAL_MODEL") or local_cfg["model"]
    base_url = local_cfg.get("base_url", "http://localhost:11434")
    local_client = SLMEngine(ollama_url=base_url, model=local_model)

    # Cloud client factory
    cloud_provider = args.cloud_provider or cloud_cfg.get("provider", "gemini")
    cloud_model = args.cloud_model or cloud_cfg.get("model")
    cloud_client = None

    needs_cloud = args.strategy in ("b3", "b4", "b5", "b6", "all", "always_cloud", "static_escalation", "selective", "frugalgpt", "automix", "peer_review", "peer", "p1", "p2")
    if needs_cloud:
        try:
            cloud_client = get_cloud_client(provider=cloud_provider, model=cloud_model)
            print(f"Cloud provider initialized: {cloud_provider} ({cloud_model or 'default'})")
        except Exception as exc:
            if args.strategy in ("b0", "b1", "b2"):
                cloud_client = None
            else:
                print(f"[Warning] Could not initialize cloud client ({exc}). Only local strategies can run.")
                if args.strategy not in ("all",):
                    raise

    strategies_to_run = ["b0", "b1", "b2", "b3", "b4", "b5"] if args.strategy == "all" else [args.strategy]
    all_results: dict[str, list[dict[str, Any]]] = {}

    for strat_id in strategies_to_run:
        try:
            strategy = build_strategy(strat_id, local_client, cloud_client, local_cfg, cloud_cfg)
        except Exception as exc:
            print(f"Skipping strategy {strat_id}: {exc}")
            continue

        print(f"\n=======================================================")
        print(f"Running strategy: {strategy.name.upper()} ({len(tasks)} tasks)")
        print(f"=======================================================")

        out_path = args.output
        if not out_path or len(strategies_to_run) > 1:
            out_path = ROOT / f"results/gsm8k_{strategy.name}.jsonl"
        elif not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        records = []
        correct = 0
        with out_path.open("w", encoding="utf-8") as handle:
            for index, task in enumerate(tasks, start=1):
                res = strategy.run(task)
                is_correct = numeric_equal(res["predicted_numeric"], task["ground_truth"])
                correct += int(is_correct)
                rec = {
                    **task,
                    **res,
                    "strategy": strategy.name,
                    "correct": is_correct,
                    "run_id": f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                    "dataset_sha256": digest,
                    "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                }
                records.append(rec)
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
                handle.flush()
                status = "OK" if is_correct else "MISS"
                cloud_flag = f"[Cloud: {res.get('cloud_calls', 0)}]" if res.get('cloud_calls', 0) > 0 else ""
                print(f"[{index:02d}/{len(tasks):02d}] {task['task_id']} {status} "
                      f"latency={res['latency_seconds']:.1f}s {cloud_flag}")

        all_results[strategy.name] = records
        metrics = compute_benchmark_metrics(records)
        print(f"\n--- Strategy {strategy.name} Results ---")
        print(f"Accuracy: {metrics['accuracy']:.1%} ({metrics['correct_count']}/{metrics['total_tasks']})")
        print(f"Median Latency: {metrics['median_latency_seconds']}s (P95: {metrics['p95_latency_seconds']}s)")
        print(f"Cloud Calls: {metrics['cloud_delegation_rate']:.1%} | Cost: ${metrics['total_cloud_cost_usd']:.5f}")
        print(f"JSONL saved to: {out_path}")

    if len(all_results) > 1:
        report_text = generate_markdown_report(all_results)
        report_path = ROOT / "results/benchmark_summary.md"
        report_path.write_text(report_text, encoding="utf-8")
        print("\n" + report_text)
        print(f"\nSummary markdown saved to: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
