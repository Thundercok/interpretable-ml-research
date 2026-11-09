"""Unit tests for the Code Review Sniper & Distillation Pipeline."""
import pytest
from pathlib import Path
from pipelines.code_distillation.hazard_gate import evaluate_diff_hazard
from pipelines.code_distillation.dpo_curator import DPOCurator, DPOContrastivePair


def test_hazard_gate_suppresses_documentation_noise():
    raw_diff = """diff --git a/README.md b/README.md
index 123..456 100644
--- a/README.md
+++ b/README.md
@@ -1,3 +1,4 @@
 # Project
+Added documentation note.
"""
    result = evaluate_diff_hazard(raw_diff)
    assert result.is_noise is True
    assert result.admitted is False
    assert result.risk_score == 0.0


def test_hazard_gate_admits_concurrency_hazard():
    raw_diff = """diff --git a/worker/pool.py b/worker/pool.py
index abc..def 100644
--- a/worker/pool.py
+++ b/worker/pool.py
@@ -10,6 +10,12 @@ class WorkerPool:
+    async def acquire_lock_and_execute(self, query):
+        async with self.lock:
+            cursor.execute(f"SELECT * FROM users WHERE id = {query}")
"""
    result = evaluate_diff_hazard(raw_diff, threshold=4.5)
    assert result.is_noise is False
    assert result.admitted is True
    assert result.risk_score >= 4.5
    assert any("concurrency_lock" in h for h in result.detected_hazards)
    assert any("sql_injection_sink" in h for h in result.detected_hazards)


def test_dpo_curator_lifecycle(tmp_path: Path):
    dpo_file = tmp_path / "test_dpo.jsonl"
    curator = DPOCurator(dpo_file)
    assert curator.count() == 0

    pair = DPOContrastivePair(
        id="sample_1",
        source_repo="test/repo",
        pr_number=101,
        category="CONCURRENCY_OR_MEMORY",
        prompt="Review this code diff.",
        teacher_cot="Found deadlock.",
        chosen="### Defect\nDeadlock.\n\n### Minimal Patch\nReorder locks.",
        rejected="LGTM! Add type hints.",
        metadata={"hazard_score": 5.0},
    )
    curator.append_pair(pair)
    assert curator.count() == 1

    records = curator.read_all()
    assert len(records) == 1
    assert records[0]["id"] == "sample_1"
    assert "LGTM" in records[0]["rejected"]
    assert "Deadlock" in records[0]["chosen"]
