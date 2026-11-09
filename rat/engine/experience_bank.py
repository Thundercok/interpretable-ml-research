"""Experience Bank & Replicate-and-Grade Engine for CHUOT.

Whenever a task escalates to Cloud, this engine:
1. Replicates: prompts the local SLM to replicate the correct reasoning trace.
2. Grades: verifies the student's replication against the gold answer using deterministic checks.
3. Distills: stores the experience record (failed draft, gold solution, learned rule, grade) into a local SQLite store.
4. Recalls: injects relevant past lessons into future local prompts to prevent future escalations for $0.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from benchmarks.selective_delegation.evaluation.step_verifier import verify_solution

logger = logging.getLogger("rat.experience_bank")

REPLICATE_PROMPT = """You previously attempted this problem and made an error.
Problem: {question}

Here is the verified reference solution from a senior expert:
{gold_solution}

Carefully study the steps. In your own words, write out the verified step-by-step reasoning that solves it correctly.
Conclude on the final line with exactly: #### number"""

DISTILL_PROMPT = """Analyze why the initial draft failed compared to the gold solution.
Problem: {question}
Initial Failed Draft: {failed_draft}
Gold Solution: {gold_solution}

State in exactly 1 concise sentence the key rule or pitfall to avoid next time:"""


@dataclass
class ExperienceRecord:
    task_id: str
    question: str
    category: str
    failed_draft: str
    gold_solution: str
    replicated_solution: str
    grade_score: float
    grade_verdict: str  # "PASS" or "FAIL"
    grade_feedback: str
    learned_rule: str
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperienceBank:
    """Persistent on-device SQLite store for lessons learned from cloud escalations."""

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            self.path = Path.home() / ".rat" / "experience_bank.db"
        else:
            self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    task_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    category TEXT NOT NULL,
                    failed_draft TEXT NOT NULL,
                    gold_solution TEXT NOT NULL,
                    replicated_solution TEXT NOT NULL,
                    grade_score REAL NOT NULL,
                    grade_verdict TEXT NOT NULL,
                    grade_feedback TEXT NOT NULL,
                    learned_rule TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON experiences(category)")

    def store(self, record: ExperienceRecord) -> None:
        if not record.created_at:
            record.created_at = time.time()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO experiences (
                    task_id, question, category, failed_draft, gold_solution,
                    replicated_solution, grade_score, grade_verdict, grade_feedback,
                    learned_rule, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.task_id,
                    record.question,
                    record.category,
                    record.failed_draft,
                    record.gold_solution,
                    record.replicated_solution,
                    record.grade_score,
                    record.grade_verdict,
                    record.grade_feedback,
                    record.learned_rule,
                    record.created_at,
                ),
            )

    def count(self) -> int:
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM experiences")
            return cursor.fetchone()[0]

    def retrieve_relevant(self, query: str, limit: int = 1) -> list[ExperienceRecord]:
        """Simple lexical word-overlap retrieval for in-context lesson injection."""
        query_words = set(re.findall(r"\w+", query.lower()))
        if not query_words:
            return []

        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM experiences ORDER BY created_at DESC LIMIT 50").fetchall()

        scored_records: list[tuple[float, ExperienceRecord]] = []
        for row in rows:
            q_words = set(re.findall(r"\w+", row["question"].lower()))
            overlap = len(query_words.intersection(q_words)) / max(len(query_words), 1)
            rec = ExperienceRecord(
                task_id=row["task_id"],
                question=row["question"],
                category=row["category"],
                failed_draft=row["failed_draft"],
                gold_solution=row["gold_solution"],
                replicated_solution=row["replicated_solution"],
                grade_score=float(row["grade_score"]),
                grade_verdict=row["grade_verdict"],
                grade_feedback=row["grade_feedback"],
                learned_rule=row["learned_rule"],
                created_at=float(row["created_at"]),
            )
            if overlap > 0.15:  # meaningful word overlap threshold
                scored_records.append((overlap, rec))

        scored_records.sort(key=lambda x: x[0], reverse=True)
        return [rec for _, rec in scored_records[:limit]]

    def format_exemplar_context(self, records: list[ExperienceRecord]) -> str:
        """Formats retrieved experiences into few-shot guidance for local prompts."""
        if not records:
            return ""
        sections = []
        for i, rec in enumerate(records, 1):
            sections.append(
                f"[Past Lesson #{i}]\n"
                f"Rule to apply: {rec.learned_rule}\n"
                f"Reference Example Question: {rec.question}\n"
                f"Correct Approach Pattern:\n{rec.gold_solution}"
            )
        return "\n\n".join(sections)


class ReplicateAndGradeEngine:
    """Drives the student replication, grading, rule extraction, and bank storage."""

    def __init__(self, bank: ExperienceBank, local_client: Any, timeout: float = 120.0):
        self.bank = bank
        self.local_client = local_client
        self.timeout = timeout

    def replicate_and_grade(
        self,
        question: str,
        failed_draft: str,
        gold_solution: str,
        category: str = "math",
        task_id: str | None = None,
    ) -> ExperienceRecord:
        task_id = task_id or str(uuid.uuid4())[:8]

        # 1. Replicate: Student attempts to produce verified solution from gold guidance
        replicate_msg = [
            {"role": "system", "content": "You are a diligent student learning to master reasoning."},
            {"role": "user", "content": REPLICATE_PROMPT.format(question=question, gold_solution=gold_solution)},
        ]
        resp_rep = self.local_client.chat_with_meta(
            replicate_msg, tools=[], timeout=self.timeout, max_tokens=1024, thinking=False
        )
        replicated_content = (resp_rep.get("message") or {}).get("content", "")

        # 2. Grade: Deterministic evaluation of replicated trajectory against gold answer
        gold_v = verify_solution(gold_solution)
        rep_v = verify_solution(replicated_content)

        gold_num = gold_v.predicted_numeric
        rep_num = rep_v.predicted_numeric

        # Grade criteria: numeric equality + equation correctness
        matches_numeric = (gold_num is not None) and (gold_num == rep_num)
        is_verified_pass = rep_v.status == "PASS"

        if matches_numeric and is_verified_pass:
            grade_score = 1.0
            grade_verdict = "PASS"
            grade_feedback = "Replication is fully sound and matches gold numeric answer."
        elif matches_numeric:
            grade_score = 0.7
            grade_verdict = "PASS"
            grade_feedback = f"Numeric answer matches ({rep_num}), but some arithmetic checks were unverified ({rep_v.reason})."
        else:
            grade_score = 0.0
            grade_verdict = "FAIL"
            grade_feedback = f"Replication answer ({rep_num}) failed to match gold ({gold_num})."

        # 3. Distill rule: Extract concise lesson
        distill_msg = [
            {"role": "system", "content": "You are an analytical tutor summarizing key learning takeaways."},
            {
                "role": "user",
                "content": DISTILL_PROMPT.format(
                    question=question, failed_draft=failed_draft, gold_solution=gold_solution
                ),
            },
        ]
        resp_distill = self.local_client.chat_with_meta(
            distill_msg, tools=[], timeout=self.timeout, max_tokens=256, thinking=False
        )
        distill_text = (resp_distill.get("message") or {}).get("content", "").strip()
        learned_rule = distill_text or f"Ensure calculations match ground-truth pattern: {gold_solution[-60:]}"

        # 4. Store in Experience Bank
        record = ExperienceRecord(
            task_id=task_id,
            question=question,
            category=category,
            failed_draft=failed_draft,
            gold_solution=gold_solution,
            replicated_solution=replicated_content,
            grade_score=grade_score,
            grade_verdict=grade_verdict,
            grade_feedback=grade_feedback,
            learned_rule=learned_rule,
            created_at=time.time(),
        )
        self.bank.store(record)
        return record
