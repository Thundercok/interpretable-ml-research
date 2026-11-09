"""B4: Static escalation strategy calling cloud whenever verification status is FAIL or UNKNOWN."""
from __future__ import annotations

import time
from typing import Any

from benchmarks.selective_delegation.clients.base import CloudModelClient
from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution
from benchmarks.selective_delegation.strategies.local_only import SYSTEM_PROMPT


class StaticEscalationStrategy:
    name = "static_escalation"

    def __init__(
        self,
        local_client: Any,
        cloud_client: CloudModelClient,
        local_max_tokens: int = 1024,
        cloud_max_tokens: int = 2048,
        timeout: float = 180.0,
    ):
        self.local_client = local_client
        self.cloud_client = cloud_client
        self.local_max_tokens = local_max_tokens
        self.cloud_max_tokens = cloud_max_tokens
        self.timeout = timeout

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        local_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["question"]},
        ]
        local_resp = self.local_client.chat_with_meta(
            local_messages, tools=[], timeout=self.timeout, max_tokens=self.local_max_tokens, thinking=False
        )
        local_content = (local_resp.get("message") or {}).get("content", "")
        v_outcome = verify_solution(local_content)

        local_p = local_resp.get("prompt_tokens", 0) or 0
        local_c = local_resp.get("completion_tokens", 0) or 0

        # If PASS: accept locally without cloud escalation
        if v_outcome.status == "PASS":
            elapsed = time.perf_counter() - started
            return {
                "final_answer": local_content,
                "predicted_numeric": v_outcome.predicted_numeric,
                "error": local_resp.get("error"),
                "local_tokens": local_p + local_c,
                "cloud_tokens": 0,
                "cloud_calls": 0,
                "cloud_cost_usd": 0.0,
                "latency_seconds": elapsed,
                "verification_status": "PASS",
                "verification_failure_type": None,
                "verification_reason": v_outcome.reason,
                "escalated": False,
                "repair_attempts": 0,
            }

        # If FAIL or UNKNOWN: statically escalate to cloud
        cloud_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{task['question']}\n\n"
                    f"[Verification Note: A local attempt was rejected with status {v_outcome.status} "
                    f"({v_outcome.reason}). Please provide a verified, rigorous solution.]"
                ),
            },
        ]
        cloud_resp = self.cloud_client.chat_with_meta(
            cloud_messages, max_tokens=self.cloud_max_tokens, temperature=0.0
        )
        elapsed = time.perf_counter() - started
        cloud_content = cloud_resp.get("content", "")
        cloud_v = verify_solution(cloud_content)

        cloud_in = cloud_resp.get("input_tokens") or 0
        cloud_out = cloud_resp.get("output_tokens") or 0

        return {
            "final_answer": cloud_content,
            "predicted_numeric": cloud_v.predicted_numeric,
            "error": cloud_resp.get("error") or local_resp.get("error"),
            "local_tokens": local_p + local_c,
            "cloud_tokens": cloud_in + cloud_out,
            "cloud_calls": 1,
            "cloud_cost_usd": cloud_resp.get("cost_usd") or 0.0,
            "cloud_provider": cloud_resp.get("provider"),
            "cloud_model": cloud_resp.get("model"),
            "latency_seconds": elapsed,
            "verification_status": cloud_v.status,
            "verification_failure_type": v_outcome.failure_type,
            "verification_reason": f"Escalated due to {v_outcome.status}: {v_outcome.reason}",
            "escalated": True,
            "repair_attempts": 0,
        }
