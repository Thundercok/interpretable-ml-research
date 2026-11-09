"""B1: Local model with one naive retry on verification failure (no structured feedback)."""
from __future__ import annotations

import time
from typing import Any

from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution
from benchmarks.selective_delegation.strategies.local_only import SYSTEM_PROMPT


class LocalRetryStrategy:
    name = "local_retry"

    def __init__(self, client: Any, max_tokens: int = 1024, timeout: float = 180.0):
        self.client = client
        self.max_tokens = max_tokens
        self.timeout = timeout

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["question"]},
        ]
        started = time.perf_counter()
        resp1 = self.client.chat_with_meta(
            messages, tools=[], timeout=self.timeout, max_tokens=self.max_tokens, thinking=False
        )
        content1 = (resp1.get("message") or {}).get("content", "")
        v1 = verify_solution(content1)

        total_prompt = resp1.get("prompt_tokens", 0) or 0
        total_comp = resp1.get("completion_tokens", 0) or 0
        repair_attempts = 0
        final_content = content1
        final_ver = v1

        # If verification fails, retry ONCE with clean original prompt (no feedback)
        if v1.status == "FAIL":
            repair_attempts = 1
            resp2 = self.client.chat_with_meta(
                messages, tools=[], timeout=self.timeout, max_tokens=self.max_tokens, thinking=False
            )
            content2 = (resp2.get("message") or {}).get("content", "")
            v2 = verify_solution(content2)
            total_prompt += resp2.get("prompt_tokens", 0) or 0
            total_comp += resp2.get("completion_tokens", 0) or 0
            final_content = content2
            final_ver = v2

        elapsed = time.perf_counter() - started
        return {
            "final_answer": final_content,
            "predicted_numeric": final_ver.predicted_numeric,
            "error": resp1.get("error"),
            "local_tokens": total_prompt + total_comp,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_comp,
            "token_usage_known": bool(resp1.get("token_usage_known", False)),
            "latency_seconds": elapsed,
            "cloud_calls": 0,
            "cloud_cost_usd": 0.0,
            "verification_status": final_ver.status,
            "verification_failure_type": final_ver.failure_type,
            "verification_reason": final_ver.reason,
            "repair_attempts": repair_attempts,
        }
