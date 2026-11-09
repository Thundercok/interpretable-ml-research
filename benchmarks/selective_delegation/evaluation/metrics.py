"""Comprehensive evaluation metrics for selective delegation benchmark."""
from __future__ import annotations

import statistics
from typing import Any


def compute_benchmark_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute primary, verification, and efficiency metrics from task records."""
    total = len(records)
    if total == 0:
        return {}

    # Primary metrics
    correct_count = sum(1 for r in records if r.get("correct") is True)
    accuracy = correct_count / total

    completed_count = sum(1 for r in records if r.get("predicted_numeric") is not None)
    completion_rate = completed_count / total

    delegated_count = sum(1 for r in records if (r.get("cloud_calls") or 0) > 0)
    cloud_delegation_rate = delegated_count / total

    total_cloud_cost = sum(r.get("cloud_cost_usd") or 0.0 for r in records)
    cost_per_task = total_cloud_cost / total

    local_success_count = sum(1 for r in records if r.get("correct") is True and (r.get("cloud_calls") or 0) == 0)
    local_only_success_rate = local_success_count / total

    # Verification metrics
    # False acceptance: verifier said PASS, but answer was actually wrong
    false_accepts = sum(1 for r in records if r.get("verification_status") == "PASS" and not r.get("correct"))
    false_accept_rate = false_accepts / total

    # False rejection: verifier said FAIL, but answer was actually correct
    false_rejects = sum(1 for r in records if r.get("verification_status") == "FAIL" and r.get("correct"))
    false_reject_rate = false_rejects / total

    unknown_count = sum(1 for r in records if r.get("verification_status") == "UNKNOWN")
    unknown_rate = unknown_count / total

    # Efficiency metrics
    latencies = [r.get("latency_seconds", 0.0) for r in records]
    med_latency = statistics.median(latencies) if latencies else 0.0
    sorted_lat = sorted(latencies)
    p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)
    p95_latency = sorted_lat[p95_idx] if sorted_lat else 0.0

    local_tokens = [r.get("local_tokens", 0) for r in records]
    avg_local_tokens = statistics.mean(local_tokens) if local_tokens else 0.0

    cloud_tokens = [r.get("cloud_tokens", 0) for r in records]
    avg_cloud_tokens = statistics.mean(cloud_tokens) if cloud_tokens else 0.0

    strategy_name = records[0].get("strategy", "unknown") if records else "unknown"

    return {
        "strategy": strategy_name,
        "total_tasks": total,
        "correct_count": correct_count,
        "accuracy": accuracy,
        "completion_rate": completion_rate,
        "cloud_delegation_rate": cloud_delegation_rate,
        "total_cloud_cost_usd": total_cloud_cost,
        "cost_per_task_usd": cost_per_task,
        "local_only_success_rate": local_only_success_rate,
        "false_acceptance_rate": false_accept_rate,
        "false_rejection_rate": false_reject_rate,
        "unknown_rate": unknown_rate,
        "median_latency_seconds": round(med_latency, 2),
        "p95_latency_seconds": round(p95_latency, 2),
        "avg_local_tokens": round(avg_local_tokens, 1),
        "avg_cloud_tokens": round(avg_cloud_tokens, 1),
    }
