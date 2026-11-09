"""FrugalGPT peer baseline: Quality-based cascading using local self-consistency agreement."""
from __future__ import annotations

import collections
import time
from typing import Any

from benchmarks.selective_delegation.clients.base import CloudModelClient
from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution
from benchmarks.selective_delegation.strategies.local_only import SYSTEM_PROMPT


class FrugalGPTStrategy:
    """FrugalGPT (Chen et al., NeurIPS 2023) cascade baseline.

    Generates k sample paths on the local model and measures consensus (agreement ratio).
    If agreement >= threshold, accepts the majority response locally ($0 cloud cost).
    If agreement < threshold, cascades the task to the cloud model.
    """

    name = "frugalgpt"

    def __init__(
        self,
        local_client: Any,
        cloud_client: CloudModelClient,
        k: int = 3,
        threshold: float = 0.66,
        local_max_tokens: int = 1024,
        cloud_max_tokens: int = 2048,
        timeout: float = 180.0,
    ):
        self.local_client = local_client
        self.cloud_client = cloud_client
        self.k = k
        self.threshold = threshold
        self.local_max_tokens = local_max_tokens
        self.cloud_max_tokens = cloud_max_tokens
        self.timeout = timeout

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["question"]},
        ]

        total_prompt_tokens = 0
        total_comp_tokens = 0
        samples: list[dict[str, Any]] = []
        numeric_answers: list[str] = []

        # Sample k paths
        for _ in range(self.k):
            resp = self.local_client.chat_with_meta(
                messages,
                tools=[],
                timeout=self.timeout,
                max_tokens=self.local_max_tokens,
                temperature=0.7 if self.k > 1 else 0.0,
                thinking=False,
            )
            content = (resp.get("message") or {}).get("content", "")
            total_prompt_tokens += resp.get("prompt_tokens", 0) or 0
            total_comp_tokens += resp.get("completion_tokens", 0) or 0

            v_res = verify_solution(content)
            samples.append({"content": content, "predicted_numeric": v_res.predicted_numeric, "verifier": v_res})
            if v_res.predicted_numeric is not None:
                numeric_answers.append(v_res.predicted_numeric)

        # Compute consensus agreement
        if numeric_answers:
            counts = collections.Counter(numeric_answers)
            majority_answer, majority_count = counts.most_common(1)[0]
            agreement_ratio = majority_count / self.k
        else:
            majority_answer = None
            majority_count = 0
            agreement_ratio = 0.0

        # If agreement satisfies threshold: Accept local majority solution
        if majority_answer is not None and agreement_ratio >= (self.threshold - 1e-4):
            elapsed = time.perf_counter() - started
            # Pick the first sample that produced the majority answer
            selected_sample = next(s for s in samples if s["predicted_numeric"] == majority_answer)
            v_selected = selected_sample["verifier"]

            return {
                "final_answer": selected_sample["content"],
                "predicted_numeric": majority_answer,
                "error": None,
                "local_tokens": total_prompt_tokens + total_comp_tokens,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_comp_tokens,
                "token_usage_known": True,
                "cloud_tokens": 0,
                "cloud_calls": 0,
                "cloud_cost_usd": 0.0,
                "latency_seconds": elapsed,
                "verification_status": v_selected.status,
                "verification_failure_type": v_selected.failure_type,
                "verification_reason": f"FrugalGPT consensus pass (agreement {agreement_ratio:.2f} >= {self.threshold})",
                "escalated": False,
                "confidence_score": agreement_ratio,
                "majority_count": majority_count,
                "k_samples": self.k,
            }

        # Otherwise: Cascade to cloud
        cloud_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{task['question']}\n\n"
                    f"[FrugalGPT Cascade: Local consensus was low ({agreement_ratio:.2f} < {self.threshold}). "
                    f"Please provide a rigorous, step-by-step solution.]"
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
            "error": cloud_resp.get("error"),
            "local_tokens": total_prompt_tokens + total_comp_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_comp_tokens,
            "token_usage_known": True,
            "cloud_tokens": cloud_in + cloud_out,
            "cloud_calls": 1,
            "cloud_cost_usd": cloud_resp.get("cost_usd") or 0.0,
            "cloud_provider": cloud_resp.get("provider"),
            "cloud_model": cloud_resp.get("model"),
            "latency_seconds": elapsed,
            "verification_status": cloud_v.status,
            "verification_failure_type": None,
            "verification_reason": f"FrugalGPT escalated: low consensus ({agreement_ratio:.2f} < {self.threshold})",
            "escalated": True,
            "confidence_score": agreement_ratio,
            "majority_count": majority_count,
            "k_samples": self.k,
        }
