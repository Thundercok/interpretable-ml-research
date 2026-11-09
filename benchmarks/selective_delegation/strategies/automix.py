"""AutoMix peer baseline: Verification-based routing using an LLM meta-verifier."""
from __future__ import annotations

import re
import time
from typing import Any

from benchmarks.selective_delegation.clients.base import CloudModelClient
from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution
from benchmarks.selective_delegation.strategies.local_only import SYSTEM_PROMPT

VERIFIER_PROMPT = """You are an impartial mathematical verifier. Read the question and candidate solution below.
Check each calculation step carefully.

Question: {question}

Candidate Solution:
{candidate_solution}

Does this candidate solution contain any arithmetic mistakes or logical errors?
Conclude your response on the final line with exactly:
VERIFICATION: PASS
or
VERIFICATION: FAIL"""


class AutoMixStrategy:
    """AutoMix (Khattab et al., 2024) baseline.

    1. Local model generates a candidate solution.
    2. Local model is prompted as a meta-verifier to evaluate the solution.
    3. If meta-verifier predicts PASS, accept locally ($0 cloud cost).
    4. If meta-verifier predicts FAIL (or is ambiguous), escalate to cloud model
       with the verifier's feedback.
    """

    name = "automix"

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
        question = task["question"]

        # Step 1: Generate initial solution with local SLM
        gen_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        resp_gen = self.local_client.chat_with_meta(
            gen_messages, tools=[], timeout=self.timeout, max_tokens=self.local_max_tokens, thinking=False
        )
        content_gen = (resp_gen.get("message") or {}).get("content", "")
        v_gen = verify_solution(content_gen)

        total_prompt_tokens = resp_gen.get("prompt_tokens", 0) or 0
        total_comp_tokens = resp_gen.get("completion_tokens", 0) or 0

        # Step 2: Query local model as LLM meta-verifier
        verifier_content_prompt = VERIFIER_PROMPT.format(question=question, candidate_solution=content_gen)
        verifier_messages = [
            {"role": "system", "content": "You are a rigorous mathematical verifier."},
            {"role": "user", "content": verifier_content_prompt},
        ]
        resp_ver = self.local_client.chat_with_meta(
            verifier_messages, tools=[], timeout=self.timeout, max_tokens=self.local_max_tokens, thinking=False
        )
        ver_text = (resp_ver.get("message") or {}).get("content", "")
        total_prompt_tokens += resp_ver.get("prompt_tokens", 0) or 0
        total_comp_tokens += resp_ver.get("completion_tokens", 0) or 0

        # Parse meta-verifier decision
        meta_decision = "FAIL"
        if re.search(r"VERIFICATION:\s*PASS", ver_text, re.IGNORECASE):
            meta_decision = "PASS"

        # Step 3: Routing decision
        if meta_decision == "PASS":
            elapsed = time.perf_counter() - started
            return {
                "final_answer": content_gen,
                "predicted_numeric": v_gen.predicted_numeric,
                "error": None,
                "local_tokens": total_prompt_tokens + total_comp_tokens,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_comp_tokens,
                "token_usage_known": True,
                "cloud_tokens": 0,
                "cloud_calls": 0,
                "cloud_cost_usd": 0.0,
                "latency_seconds": elapsed,
                "verification_status": v_gen.status,
                "verification_failure_type": v_gen.failure_type,
                "verification_reason": f"AutoMix meta-verifier passed: {v_gen.reason}",
                "escalated": False,
                "meta_verifier_decision": "PASS",
                "meta_verifier_feedback": ver_text,
            }

        # Step 4: Escalate to Cloud on meta-verifier FAIL
        cloud_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{question}\n\n"
                    f"[AutoMix Escalation: Local solution was flagged by meta-verifier:\n"
                    f"{ver_text}\n"
                    f"Please provide an accurate, step-by-step verified solution.]"
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
            "verification_failure_type": v_gen.failure_type,
            "verification_reason": f"AutoMix escalated due to meta-verifier {meta_decision}",
            "escalated": True,
            "meta_verifier_decision": meta_decision,
            "meta_verifier_feedback": ver_text,
        }
