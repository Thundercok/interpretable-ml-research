"""Local Peer Review strategy: Proposer-Critic multi-agent review loop before escalation."""
from __future__ import annotations

import re
import time
from typing import Any

from benchmarks.selective_delegation.clients.base import CloudModelClient
from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution
from benchmarks.selective_delegation.strategies.local_only import SYSTEM_PROMPT
from rat.engine.experience_bank import ExperienceBank, ReplicateAndGradeEngine

CRITIC_PROMPT = """You are a rigorous mathematical peer reviewer.
Read the problem and the proposer's draft solution.
Check every arithmetic step, equation balance, and logic flow.

Problem: {question}

Proposer's Draft:
{proposer_content}

If the solution is fully correct, conclude on the final line with:
REVIEW: PASS

If there is an error, point out the exact calculation mistake and conclude on the final line with:
REVIEW: REVISE"""


class LocalPeerReviewStrategy:
    """Proposer-Critic local collaboration strategy.

    1. Proposer SLM generates initial candidate solution.
    2. Deterministic verifier checks it. If PASS, accept immediately ($0 cost).
    3. If verifier is FAIL/UNKNOWN, Critic SLM conducts peer review.
    4. If Critic requests REVISE, Proposer attempts revision incorporating feedback.
    5. If peer review resolves the problem (verifier PASS), accept locally.
    6. If still failing, escalate to Cloud with the peer review trace.
    """

    name = "peer_review"

    def __init__(
        self,
        local_client: Any,
        cloud_client: CloudModelClient,
        local_max_tokens: int = 1024,
        cloud_max_tokens: int = 2048,
        timeout: float = 180.0,
        max_revisions: int = 1,
        experience_bank: ExperienceBank | None = None,
        learner: ReplicateAndGradeEngine | None = None,
        auto_learn: bool = True,
    ):
        self.local_client = local_client
        self.cloud_client = cloud_client
        self.local_max_tokens = local_max_tokens
        self.cloud_max_tokens = cloud_max_tokens
        self.timeout = timeout
        self.max_revisions = max_revisions
        self.experience_bank = experience_bank
        if experience_bank is not None and learner is None and auto_learn:
            self.learner = ReplicateAndGradeEngine(experience_bank, local_client, timeout=timeout)
        else:
            self.learner = learner

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        question = task["question"]

        total_prompt_tokens = 0
        total_comp_tokens = 0
        peer_revisions = 0
        peer_saved_escalation = False
        exemplar_context = ""

        # Step 0: Recall relevant past lessons from ExperienceBank
        if self.experience_bank:
            relevant = self.experience_bank.retrieve_relevant(question, limit=1)
            if relevant:
                exemplar_context = self.experience_bank.format_exemplar_context(relevant)

        user_content = question
        if exemplar_context:
            user_content = f"{question}\n\n[In-Context Memory Guidance from Past Lesson]\n{exemplar_context}"

        # Phase 1: Proposer initial generation
        proposer_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        resp_prop = self.local_client.chat_with_meta(
            proposer_messages, tools=[], timeout=self.timeout, max_tokens=self.local_max_tokens, thinking=False
        )
        prop_content = (resp_prop.get("message") or {}).get("content", "")
        v_prop = verify_solution(prop_content)

        total_prompt_tokens += resp_prop.get("prompt_tokens", 0) or 0
        total_comp_tokens += resp_prop.get("completion_tokens", 0) or 0

        # If deterministic verifier passes immediately -> Accept locally
        if v_prop.status == "PASS":
            elapsed = time.perf_counter() - started
            return {
                "final_answer": prop_content,
                "predicted_numeric": v_prop.predicted_numeric,
                "error": None,
                "local_tokens": total_prompt_tokens + total_comp_tokens,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_comp_tokens,
                "token_usage_known": True,
                "cloud_tokens": 0,
                "cloud_calls": 0,
                "cloud_cost_usd": 0.0,
                "latency_seconds": elapsed,
                "verification_status": "PASS",
                "verification_failure_type": None,
                "verification_reason": "Immediate proposer pass",
                "escalated": False,
                "peer_revisions": 0,
                "peer_saved_escalation": False,
                "recalled_exemplar": bool(exemplar_context),
            }

        # Phase 2: Critic Review
        critic_input = CRITIC_PROMPT.format(question=question, proposer_content=prop_content)
        critic_messages = [
            {"role": "system", "content": "You are a precise, critical mathematical auditor."},
            {"role": "user", "content": critic_input},
        ]
        resp_critic = self.local_client.chat_with_meta(
            critic_messages, tools=[], timeout=self.timeout, max_tokens=self.local_max_tokens, thinking=False
        )
        critic_text = (resp_critic.get("message") or {}).get("content", "")
        total_prompt_tokens += resp_critic.get("prompt_tokens", 0) or 0
        total_comp_tokens += resp_critic.get("completion_tokens", 0) or 0

        current_content = prop_content
        current_v = v_prop

        # Check if Critic spotted an issue and requested revision
        needs_revision = bool(re.search(r"REVIEW:\s*REVISE", critic_text, re.IGNORECASE))

        # Phase 3: Proposer Revision using Critic feedback
        if needs_revision and peer_revisions < self.max_revisions:
            peer_revisions += 1
            revision_messages = list(proposer_messages)
            revision_messages.append({"role": "assistant", "content": prop_content})
            revision_messages.append({
                "role": "user",
                "content": (
                    f"Your peer reviewer checked your draft and provided this critique:\n"
                    f"{critic_text}\n\n"
                    f"Please address this feedback, correct any calculation errors, and provide the revised solution. "
                    f"Conclude on the final line with: #### number."
                ),
            })
            resp_rev = self.local_client.chat_with_meta(
                revision_messages, tools=[], timeout=self.timeout, max_tokens=self.local_max_tokens, thinking=False
            )
            rev_content = (resp_rev.get("message") or {}).get("content", "")
            current_v = verify_solution(rev_content)
            current_content = rev_content

            total_prompt_tokens += resp_rev.get("prompt_tokens", 0) or 0
            total_comp_tokens += resp_rev.get("completion_tokens", 0) or 0

            # If peer revision cured the error -> Accept locally
            if current_v.status == "PASS":
                peer_saved_escalation = True
                elapsed = time.perf_counter() - started
                return {
                    "final_answer": current_content,
                    "predicted_numeric": current_v.predicted_numeric,
                    "error": None,
                    "local_tokens": total_prompt_tokens + total_comp_tokens,
                    "prompt_tokens": total_prompt_tokens,
                    "completion_tokens": total_comp_tokens,
                    "token_usage_known": True,
                    "cloud_tokens": 0,
                    "cloud_calls": 0,
                    "cloud_cost_usd": 0.0,
                    "latency_seconds": elapsed,
                    "verification_status": "PASS",
                    "verification_failure_type": None,
                    "verification_reason": "Peer review revised and verified successfully",
                    "escalated": False,
                    "peer_revisions": peer_revisions,
                    "peer_saved_escalation": True,
                    "critic_feedback": critic_text,
                    "recalled_exemplar": bool(exemplar_context),
                }

        # Phase 4: Escalation to Cloud if peer review still failed
        cloud_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{question}\n\n"
                    f"[Peer Review Escalation Note: Local proposer and critic attempted this problem but "
                    f"failed verification ({current_v.status}: {current_v.reason}).\n"
                    f"Critic critique:\n{critic_text}\n"
                    f"Please provide an authoritative, step-by-step verified solution.]"
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

        # Post-Escalation Learning: Trigger Replicate & Grade
        learned_rule = None
        grade_verdict = None
        if self.learner and cloud_content:
            try:
                rec = self.learner.replicate_and_grade(
                    question=question,
                    failed_draft=current_content,
                    gold_solution=cloud_content,
                    task_id=task.get("id"),
                )
                learned_rule = rec.learned_rule
                grade_verdict = rec.grade_verdict
            except Exception:
                pass

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
            "verification_failure_type": current_v.failure_type,
            "verification_reason": f"Escalated after peer review: {current_v.reason}",
            "escalated": True,
            "peer_revisions": peer_revisions,
            "peer_saved_escalation": False,
            "critic_feedback": critic_text,
            "learned_rule": learned_rule,
            "grade_verdict": grade_verdict,
            "recalled_exemplar": bool(exemplar_context),
        }
