"""Verification layer for arithmetic reasoning steps in math word problems."""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from benchmarks.selective_delegation.strategies.local_only import extract_numeric_answer
from rat.engine.verification import evaluate_expression


@dataclass
class VerificationOutcome:
    status: str  # "PASS", "FAIL", "UNKNOWN"
    failure_type: str | None  # "syntax", "arithmetic", "unresolved"
    reason: str
    equations_checked: int
    equations_failed: list[str]
    predicted_numeric: str | None
    feedback_prompt: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "failure_type": self.failure_type,
            "reason": self.reason,
            "equations_checked": self.equations_checked,
            "equations_failed": self.equations_failed,
            "predicted_numeric": self.predicted_numeric,
        }


def extract_equations(text: str) -> list[tuple[str, str, str]]:
    """
    Extract candidates of the form (full_match, lhs, rhs) where lhs is an expression
    and rhs is a numeric value.
    """
    # Matches patterns like: 430 + 320 = 750 or 25 * 4 = 100
    pattern = r"(\b\d[\d\s\+\-\*\/\(\)\.]*?)\s*=\s*([-+]?[0-9]+(?:\.[0-9]+)?)\b"
    candidates = []
    for match in re.finditer(pattern, text):
        lhs = match.group(1).strip()
        rhs = match.group(2).strip()
        # Ensure lhs contains an actual operator
        if any(op in lhs for op in ("+", "-", "*", "/")):
            candidates.append((match.group(0), lhs, rhs))
    return candidates


def verify_solution(text: str) -> VerificationOutcome:
    """
    Formally verify reasoning text:
    1. Parse final numeric answer (syntax check).
    2. Extract and verify intermediate arithmetic equations with symbolic rational evaluation.
    """
    predicted_numeric = extract_numeric_answer(text)
    if not predicted_numeric:
        return VerificationOutcome(
            status="FAIL",
            failure_type="syntax",
            reason="Missing or unparseable final answer on the last line (expected #### number)",
            equations_checked=0,
            equations_failed=[],
            predicted_numeric=None,
            feedback_prompt=(
                "Your previous response did not include a valid final numeric answer on the last line. "
                "Please state your final numeric answer on the last line exactly as: #### number."
            ),
        )

    equations = extract_equations(text)
    if not equations:
        return VerificationOutcome(
            status="UNKNOWN",
            failure_type="unresolved",
            reason="No explicit arithmetic equations found in reasoning trace to verify",
            equations_checked=0,
            equations_failed=[],
            predicted_numeric=predicted_numeric,
            feedback_prompt=None,
        )

    failed = []
    checked_count = 0

    for full, lhs, rhs in equations:
        try:
            expected = evaluate_expression(lhs)
            cand = Fraction(rhs)
            checked_count += 1
            if expected != cand:
                failed.append(f"{lhs} = {rhs} (evaluated: {float(expected):.4g})")
        except Exception:
            # If expression syntax is not supported by evaluator, skip that equation
            continue

    if failed:
        first_err = failed[0]
        return VerificationOutcome(
            status="FAIL",
            failure_type="arithmetic",
            reason=f"Arithmetic check failed in {len(failed)} step(s): {first_err}",
            equations_checked=checked_count,
            equations_failed=failed,
            predicted_numeric=predicted_numeric,
            feedback_prompt=(
                f"Your calculation contains an arithmetic error: {first_err}. "
                "Please review your calculations, correct the error, and state the final numeric answer on the last line as: #### number."
            ),
        )

    if checked_count > 0:
        return VerificationOutcome(
            status="PASS",
            failure_type=None,
            reason=f"Verified {checked_count} intermediate arithmetic step(s) with rational arithmetic",
            equations_checked=checked_count,
            equations_failed=[],
            predicted_numeric=predicted_numeric,
            feedback_prompt=None,
        )

    return VerificationOutcome(
        status="UNKNOWN",
        failure_type="unresolved",
        reason="Equations could not be parsed into verifiable arithmetic syntax",
        equations_checked=0,
        equations_failed=[],
        predicted_numeric=predicted_numeric,
        feedback_prompt=None,
    )
