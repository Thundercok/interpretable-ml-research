"""B3: Always-cloud strategy sending all tasks directly to frontier cloud model."""
from __future__ import annotations

import time
from typing import Any

from benchmarks.selective_delegation.clients.base import CloudModelClient
from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution
from benchmarks.selective_delegation.strategies.local_only import SYSTEM_PROMPT


class AlwaysCloudStrategy:
    name = "always_cloud"

    def __init__(self, cloud_client: CloudModelClient, max_tokens: int = 2048, temperature: float = 0.0):
        self.cloud_client = cloud_client
        self.max_tokens = max_tokens
        self.temperature = temperature

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["question"]},
        ]
        started = time.perf_counter()
        resp = self.cloud_client.chat_with_meta(
            messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        elapsed = time.perf_counter() - started
        content = resp.get("content", "")
        v_outcome = verify_solution(content)

        input_toks = resp.get("input_tokens") or 0
        output_toks = resp.get("output_tokens") or 0

        return {
            "final_answer": content,
            "predicted_numeric": v_outcome.predicted_numeric,
            "error": resp.get("error"),
            "local_tokens": 0,
            "prompt_tokens": input_toks,
            "completion_tokens": output_toks,
            "cloud_tokens": input_toks + output_toks,
            "token_usage_known": (input_toks > 0 or output_toks > 0),
            "latency_seconds": elapsed,
            "cloud_calls": 1,
            "cloud_cost_usd": resp.get("cost_usd") or 0.0,
            "cloud_provider": resp.get("provider"),
            "cloud_model": resp.get("model"),
            "verification_status": v_outcome.status,
            "verification_failure_type": v_outcome.failure_type,
            "verification_reason": v_outcome.reason,
            "repair_attempts": 0,
        }
