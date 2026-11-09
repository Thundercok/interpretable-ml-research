"""B2: Local model with structured verification feedback repair (up to 2 attempts)."""
from __future__ import annotations

import time
from typing import Any

from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution
from benchmarks.selective_delegation.strategies.local_only import SYSTEM_PROMPT


class VerifiedRepairStrategy:
    name = "verified_repair"

    def __init__(self, client: Any, max_tokens: int = 1024, timeout: float = 180.0, max_repairs: int = 2):
        self.client = client
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_repairs = max_repairs

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["question"]},
        ]
        started = time.perf_counter()
        resp = self.client.chat_with_meta(
            messages, tools=[], timeout=self.timeout, max_tokens=self.max_tokens, thinking=False
        )
        content = (resp.get("message") or {}).get("content", "")
        v_outcome = verify_solution(content)

        total_prompt = resp.get("prompt_tokens", 0) or 0
        total_comp = resp.get("completion_tokens", 0) or 0
        repair_attempts = 0

        # Conversation history for iterative repairs
        history = list(messages)
        history.append({"role": "assistant", "content": content})

        while v_outcome.status == "FAIL" and repair_attempts < self.max_repairs:
            feedback = v_outcome.feedback_prompt or (
                "Verification failed. Please review your calculations step by step, "
                "correct any errors, and state the final answer on the last line as: #### number."
            )
            history.append({"role": "user", "content": feedback})
            repair_attempts += 1

            resp = self.client.chat_with_meta(
                history, tools=[], timeout=self.timeout, max_tokens=self.max_tokens, thinking=False
            )
            content = (resp.get("message") or {}).get("content", "")
            history.append({"role": "assistant", "content": content})
            v_outcome = verify_solution(content)

            total_prompt += resp.get("prompt_tokens", 0) or 0
            total_comp += resp.get("completion_tokens", 0) or 0

        elapsed = time.perf_counter() - started
        return {
            "final_answer": content,
            "predicted_numeric": v_outcome.predicted_numeric,
            "error": resp.get("error"),
            "local_tokens": total_prompt + total_comp,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_comp,
            "token_usage_known": bool(resp.get("token_usage_known", False)),
            "latency_seconds": elapsed,
            "cloud_calls": 0,
            "cloud_cost_usd": 0.0,
            "verification_status": v_outcome.status,
            "verification_failure_type": v_outcome.failure_type,
            "verification_reason": v_outcome.reason,
            "repair_attempts": repair_attempts,
        }
