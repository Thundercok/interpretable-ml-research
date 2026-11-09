"""
tests/test_code_review_capability.py — Verification of RAT Code Review Capability.

Tests unified diff parsing, multi-lens inspection (missing imports, boundary invariants,
hygiene, secrets), GitHub PR markdown rendering, and registry integration.
"""
from __future__ import annotations

import pytest

from rat.kernel.capabilities import build_core_registry
from rat.kernel.capabilities.code_review import (
    DiffFile,
    analyze_diff_files,
    create_code_review_capability,
    determine_verdict,
    parse_unified_diff,
    render_pr_review_markdown,
)


SAMPLE_BFS_DIFF_WITH_MISSING_IMPORT = """diff --git a/graphs/search.py b/graphs/search.py
index 1234567..89abcdef 100644
--- a/graphs/search.py
+++ b/graphs/search.py
@@ -1,6 +1,9 @@
-def placeholder():
-    pass
+def node_query(graph, start_node, distance: int):
+    visited = set([start_node])
+    queue = deque([(start_node, 0)])
+    res = []
+    while queue:
+        curr, d = queue.popleft()
+        if d <= distance:
+            res.append(curr)
+    return res
"""

SAMPLE_DIFF_WITH_DOCSTRING_REMOVAL = """diff --git a/utils/math.py b/utils/math.py
index aaaaaaa..bbbbbbb 100644
--- a/utils/math.py
+++ b/utils/math.py
@@ -1,5 +1,2 @@
 def calculate_area(radius):
-    \"\"\"Calculate area of circle from radius.\"\"\"
     return 3.14159 * radius * radius
"""

SAMPLE_DIFF_WITH_SECRET = """diff --git a/config.py b/config.py
index 1111111..2222222 100644
--- a/config.py
+++ b/config.py
@@ -1,2 +1,3 @@
+api_key = "sk-1234567890abcdef1234567890abcdef12"
"""


def test_diff_parser_extracts_files_and_lines():
    files = parse_unified_diff(SAMPLE_BFS_DIFF_WITH_MISSING_IMPORT)
    assert len(files) == 1
    file = files[0]
    assert file.new_path == "graphs/search.py"
    assert file.language == "python"
    assert len(file.hunks) == 1
    assert len(file.added_lines) == 9
    assert file.added_lines[0] == (1, "def node_query(graph, start_node, distance: int):")
    assert file.added_lines[2] == (3, "    queue = deque([(start_node, 0)])")


def test_detects_missing_deque_import():
    """Reproduces the real-world bug detected in Madeira-Mod2-CSII/graphs_workshop#5."""
    files = parse_unified_diff(SAMPLE_BFS_DIFF_WITH_MISSING_IMPORT)
    findings = analyze_diff_files(files)

    # Must catch missing deque import as CRITICAL
    crit = [f for f in findings if f.severity == "CRITICAL" and "deque" in f.title]
    assert len(crit) == 1
    assert crit[0].lens == "correctness"
    assert crit[0].line_number == 3
    assert crit[0].suggested_fix == "from collections import deque"


def test_detects_missing_distance_boundary_check():
    """Verifies invariant check on distance parameter."""
    files = parse_unified_diff(SAMPLE_BFS_DIFF_WITH_MISSING_IMPORT)
    findings = analyze_diff_files(files)

    invariants = [f for f in findings if f.lens == "invariants"]
    assert any("distance" in f.title.lower() for f in invariants)


def test_no_false_positive_when_import_present():
    clean_diff = """diff --git a/graphs/search.py b/graphs/search.py
index 1234567..89abcdef 100644
--- a/graphs/search.py
+++ b/graphs/search.py
@@ -1,3 +1,6 @@
+from collections import deque
+
 def node_query(graph, start_node, distance: int):
+    if distance < 0:
+        return []
     queue = deque([(start_node, 0)])
"""
    files = parse_unified_diff(clean_diff)
    findings = analyze_diff_files(files)

    # deque is imported and distance is bounded, so 0 critical/invariant findings
    assert not any(f.severity == "CRITICAL" for f in findings)
    assert not any(f.lens == "invariants" for f in findings)


def test_detects_docstring_removal():
    files = parse_unified_diff(SAMPLE_DIFF_WITH_DOCSTRING_REMOVAL)
    findings = analyze_diff_files(files)

    doc_warnings = [f for f in findings if "docstring" in f.title.lower()]
    assert len(doc_warnings) == 1
    assert doc_warnings[0].severity == "WARNING"


def test_detects_secret_leak():
    files = parse_unified_diff(SAMPLE_DIFF_WITH_SECRET)
    findings = analyze_diff_files(files)

    sec_crit = [f for f in findings if f.lens == "security"]
    assert len(sec_crit) == 1
    assert sec_crit[0].severity == "CRITICAL"


def test_render_pr_review_markdown_formatting():
    files = parse_unified_diff(SAMPLE_BFS_DIFF_WITH_MISSING_IMPORT)
    findings = analyze_diff_files(files)
    verdict, summary = determine_verdict(findings)

    assert verdict == "CHANGES_REQUESTED"
    md = render_pr_review_markdown(
        target_name="Madeira-Mod2-CSII/graphs_workshop#5",
        verdict=verdict,
        verdict_summary=summary,
        findings=findings,
        total_files=1,
    )

    assert "## 🐀 RAT Automated Code Review" in md
    assert "CHANGES_REQUESTED" in md
    assert "from collections import deque" in md
    assert "graphs/search.py:3" in md


def test_core_registry_includes_code_review_capability():
    registry = build_core_registry()
    cap = registry.get_capability("code_review")
    assert cap is not None
    assert "review_local_diff" in cap.operations
    assert "review_github_pr" in cap.operations
