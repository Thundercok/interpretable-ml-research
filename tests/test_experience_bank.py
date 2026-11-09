"""Unit tests for ExperienceBank and ReplicateAndGradeEngine."""
import pytest
from pathlib import Path
from rat.engine.experience_bank import ExperienceBank, ExperienceRecord, ReplicateAndGradeEngine


class MockClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    def chat_with_meta(self, messages, tools=None, **kwargs):
        self.call_count += 1
        content = self.responses.pop(0) if self.responses else "Default response"
        return {
            "message": {"content": content},
            "prompt_tokens": 25,
            "completion_tokens": 15,
            "error": None,
        }


def test_experience_bank_store_and_retrieve(tmp_path: Path):
    db_file = tmp_path / "test_bank.db"
    bank = ExperienceBank(db_file)
    assert bank.count() == 0

    rec = ExperienceRecord(
        task_id="t1",
        question="Janet has 16 eggs and buys 4 more. How many eggs does she have?",
        category="math",
        failed_draft="Janet has 16 + 4 = 18 eggs.\n#### 18",
        gold_solution="16 + 4 = 20.\n#### 20",
        replicated_solution="16 + 4 = 20.\n#### 20",
        grade_score=1.0,
        grade_verdict="PASS",
        grade_feedback="Perfect replication",
        learned_rule="Double check single digit additions without skipping carries.",
    )
    bank.store(rec)
    assert bank.count() == 1

    # Query with semantic word overlap
    retrieved = bank.retrieve_relevant("Janet buys eggs at the store", limit=1)
    assert len(retrieved) == 1
    assert retrieved[0].task_id == "t1"
    assert "Double check" in retrieved[0].learned_rule

    # Format context check
    context = bank.format_exemplar_context(retrieved)
    assert "[Past Lesson #1]" in context
    assert "Double check single digit additions" in context


def test_replicate_and_grade_pass(tmp_path: Path):
    db_file = tmp_path / "test_bank2.db"
    bank = ExperienceBank(db_file)

    # Call 1: replication attempt (matches gold 25)
    # Call 2: rule distillation
    client = MockClient([
        "Step by step: 5 * 5 = 25\n#### 25",
        "Rule: When multiplying 5 by 5, output 25.",
    ])

    engine = ReplicateAndGradeEngine(bank, client)
    rec = engine.replicate_and_grade(
        question="What is 5 times 5?",
        failed_draft="5 * 5 = 30\n#### 30",
        gold_solution="5 * 5 = 25\n#### 25",
        task_id="task_math_5x5",
    )

    assert rec.grade_verdict == "PASS"
    assert rec.grade_score == 1.0
    assert rec.learned_rule == "Rule: When multiplying 5 by 5, output 25."
    assert bank.count() == 1
    assert client.call_count == 2


def test_replicate_and_grade_fail(tmp_path: Path):
    db_file = tmp_path / "test_bank3.db"
    bank = ExperienceBank(db_file)

    # Call 1: replication attempt fails (outputs 99 instead of gold 50)
    # Call 2: rule distillation
    client = MockClient([
        "I think it is:\n#### 99",
        "Rule: Be careful with large sums.",
    ])

    engine = ReplicateAndGradeEngine(bank, client)
    rec = engine.replicate_and_grade(
        question="What is 25 + 25?",
        failed_draft="25 + 25 = 40\n#### 40",
        gold_solution="25 + 25 = 50\n#### 50",
    )

    assert rec.grade_verdict == "FAIL"
    assert rec.grade_score == 0.0
    assert "failed to match gold" in rec.grade_feedback
    assert bank.count() == 1
