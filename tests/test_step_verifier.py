"""Tests for step_verifier module."""
from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution


def test_syntax_fail_when_no_answer():
    outcome = verify_solution("I don't know the answer.")
    assert outcome.status == "FAIL"
    assert outcome.failure_type == "syntax"
    assert outcome.feedback_prompt is not None


def test_arithmetic_pass():
    text = (
        "Alice has 5 apples and buys 3 more.\n"
        "5 + 3 = 8\n"
        "Then she eats 2: 8 - 2 = 6\n"
        "#### 6"
    )
    outcome = verify_solution(text)
    assert outcome.status == "PASS"
    assert outcome.equations_checked == 2
    assert outcome.predicted_numeric == "6"
    assert outcome.failure_type is None


def test_arithmetic_fail():
    text = (
        "Alice has 5 apples and buys 3 more.\n"
        "5 + 3 = 9\n"
        "#### 9"
    )
    outcome = verify_solution(text)
    assert outcome.status == "FAIL"
    assert outcome.failure_type == "arithmetic"
    assert "5 + 3 = 9" in outcome.reason
    assert outcome.feedback_prompt is not None


def test_unknown_when_no_equations():
    text = "The answer is obviously 42 because of reasons.\n#### 42"
    outcome = verify_solution(text)
    assert outcome.status == "UNKNOWN"
    assert outcome.failure_type == "unresolved"
    assert outcome.predicted_numeric == "42"
