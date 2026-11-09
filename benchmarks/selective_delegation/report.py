"""Report generator and Pareto comparison for selective delegation benchmarks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmarks.selective_delegation.evaluation.metrics import compute_benchmark_metrics


def generate_markdown_report(results_by_strategy: dict[str, list[dict[str, Any]]]) -> str:
    """Generate a clean markdown comparison table and summary."""
    summaries = []
    for strat, records in results_by_strategy.items():
        if records:
            summaries.append(compute_benchmark_metrics(records))

    if not summaries:
        return "No results available to report."

    lines = [
        "# CHUOT Benchmark v1 — Strategy Comparison Report",
        "",
        "| Strategy | Accuracy | Cost/Task ($) | Cloud Rate | Local Success | False Accept | Median Lat (s) | P95 Lat (s) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for s in summaries:
        lines.append(
            f"| `{s['strategy']}` | **{s['accuracy']:.1%}** ({s['correct_count']}/{s['total_tasks']}) | "
            f"${s['cost_per_task_usd']:.5f} | {s['cloud_delegation_rate']:.1%} | "
            f"{s['local_only_success_rate']:.1%} | {s['false_acceptance_rate']:.1%} | "
            f"{s['median_latency_seconds']:.1f}s | {s['p95_latency_seconds']:.1f}s |"
        )

    lines.extend([
        "",
        "### Key Hypotheses Check:",
        "- **H1 (Accuracy)**: Does Selective Delegation achieve higher accuracy than Local-only?",
        "- **H2 (Efficiency)**: Does Selective Delegation reduce cloud calls/cost relative to Always-cloud / Static Escalation?",
        "- **H3 (Verification Value)**: Does structured verification feedback reduce regressions?",
        "",
    ])

    return "\n".join(lines)
