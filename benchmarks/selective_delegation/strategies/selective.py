"""B5: Verification-guided selective delegation policy for multi-step reasoning."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from benchmarks.selective_delegation.clients.base import CloudModelClient
from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution
from benchmarks.selective_delegation.strategies.local_only import SYSTEM_PROMPT

ActionType = Literal["ACCEPT", "REPAIR_LOCAL", "DELEGATE", "ABSTAIN"]


@dataclass
class DelegationState:
    verification_status: str  # "PASS", "FAIL", "UNKNOWN"
    failure_type: str | None  # "syntax", "arithmetic", "unresolved"
    repair_attempts: int
    equations_checked: int
    local_tokens: int
    latency_seconds: float
    budget_remaining: float


@dataclass
class DecisionRecord:
    step: int
    action: ActionType
    reason_code: str
    verification_status: str
    failure_type: str | None
    latency_seconds: float


class SelectiveDelegationPolicy:
    """Interpretable, evidence-driven policy deciding whether to accept, repair locally, or delegate."""

    def decide(self, state: DelegationState) -> tuple[ActionType, str]:
        # Rule 1: Verified arithmetic steps pass without contradiction -> Accept locally
        if state.verification_status == "PASS":
            return "ACCEPT", "verified_local_pass"

        # Rule 2: Unknown / unformalized trace -> Allow 1 local clarification/step repair before delegating
        if state.verification_status == "UNKNOWN":
            if state.repair_attempts == 0:
                return "REPAIR_LOCAL", "unknown_attempt_first_clarification"
            return "DELEGATE", "unknown_exhausted_local_clarification"

        # Rule 3: Explicit arithmetic error detected -> Repair locally up to 2 times
        if state.verification_status == "FAIL":
            if state.failure_type == "arithmetic" and state.repair_attempts < 2:
                return "REPAIR_LOCAL", "arithmetic_local_repair"
            if state.failure_type == "syntax" and state.repair_attempts == 0:
                return "REPAIR_LOCAL", "syntax_format_repair"
            # If semantic mismatch or local repairs exhausted -> Delegate to cloud
            return "DELEGATE", "verification_failed_escalate_to_frontier"

        return "DELEGATE", "default_fallback_delegation"


class SelectiveStrategy:
    name = "selective"

    def __init__(
        self,
        local_client: Any,
        cloud_client: CloudModelClient,
        policy: SelectiveDelegationPolicy | None = None,
        local_max_tokens: int = 1024,
        cloud_max_tokens: int = 2048,
        timeout: float = 180.0,
        max_repairs: int = 2,
    ):
        self.local_client = local_client
        self.cloud_client = cloud_client
        self.policy = policy or SelectiveDelegationPolicy()
        self.local_max_tokens = local_max_tokens
        self.cloud_max_tokens = cloud_max_tokens
        self.timeout = timeout
        self.max_repairs = max_repairs

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["question"]},
        ]
        history = list(messages)

        resp = self.local_client.chat_with_meta(
            history, tools=[], timeout=self.timeout, max_tokens=self.local_max_tokens, thinking=False
        )
        content = (resp.get("message") or {}).get("content", "")
        history.append({"role": "assistant", "content": content})

        local_p = resp.get("prompt_tokens", 0) or 0
        local_c = resp.get("completion_tokens", 0) or 0
        repair_attempts = 0
        cloud_calls = 0
        cloud_cost_usd = 0.0
        cloud_tokens = 0
        decision_trace: list[dict[str, Any]] = []

        v_outcome = verify_solution(content)

        while True:
            elapsed = time.perf_counter() - started
            state = DelegationState(
                verification_status=v_outcome.status,
                failure_type=v_outcome.failure_type,
                repair_attempts=repair_attempts,
                equations_checked=v_outcome.equations_checked,
                local_tokens=local_p + local_c,
                latency_seconds=elapsed,
                budget_remaining=max(0.0, 300.0 - elapsed),
            )
            action, reason_code = self.policy.decide(state)
            decision_trace.append({
                "step": len(decision_trace) + 1,
                "action": action,
                "reason_code": reason_code,
                "verification_status": v_outcome.status,
                "failure_type": v_outcome.failure_type,
                "latency_seconds": round(elapsed, 2),
            })

            if action == "ACCEPT":
                break

            if action == "REPAIR_LOCAL" and repair_attempts < self.max_repairs:
                repair_attempts += 1
                feedback = v_outcome.feedback_prompt or (
                    "Please double check your arithmetic calculations step by step "
                    "and provide the final answer as #### number."
                )
                history.append({"role": "user", "content": feedback})
                resp = self.local_client.chat_with_meta(
                    history, tools=[], timeout=self.timeout, max_tokens=self.local_max_tokens, thinking=False
                )
                content = (resp.get("message") or {}).get("content", "")
                history.append({"role": "assistant", "content": content})
                local_p += resp.get("prompt_tokens", 0) or 0
                local_c += resp.get("completion_tokens", 0) or 0
                v_outcome = verify_solution(content)
                continue

            if action == "DELEGATE":
                cloud_calls = 1
                # Format failure context for the frontier cloud model
                failure_note = (
                    f"A local model attempted this task but failed verification with status {v_outcome.status} "
                    f"({v_outcome.reason}). Please provide the complete correct solution with #### number."
                )
                cloud_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{task['question']}\n\n[Context: {failure_note}]"},
                ]
                cloud_resp = self.cloud_client.chat_with_meta(
                    cloud_messages, max_tokens=self.cloud_max_tokens, temperature=0.0
                )
                content = cloud_resp.get("content", "")
                cloud_tokens = (cloud_resp.get("input_tokens") or 0) + (cloud_resp.get("output_tokens") or 0)
                cloud_cost_usd = cloud_resp.get("cost_usd") or 0.0
                v_outcome = verify_solution(content)
                decision_trace.append({
                    "step": len(decision_trace) + 1,
                    "action": "CLOUD_RESOLVED",
                    "reason_code": "cloud_returned_final_solution",
                    "verification_status": v_outcome.status,
                    "failure_type": v_outcome.failure_type,
                    "latency_seconds": round(time.perf_counter() - started, 2),
                })
                break

            # Fallback break for ABSTAIN
            break

        total_latency = time.perf_counter() - started
        return {
            "final_answer": content,
            "predicted_numeric": v_outcome.predicted_numeric,
            "error": resp.get("error"),
            "local_tokens": local_p + local_c,
            "cloud_tokens": cloud_tokens,
            "cloud_calls": cloud_calls,
            "cloud_cost_usd": cloud_cost_usd,
            "latency_seconds": total_latency,
            "verification_status": v_outcome.status,
            "verification_failure_type": v_outcome.failure_type,
            "verification_reason": v_outcome.reason,
            "repair_attempts": repair_attempts,
            "decision_trace": decision_trace,
        }
