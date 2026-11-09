"""
rat.kernel.capabilities.code_review — Automated Multi-Lens Code Review Capability.

Provides structured code review for local diffs and GitHub Pull Requests,
inspired by the SoL-Pi (Pi Agent) review methodology.

Lenses:
1. Correctness & Missing Imports (catches NameError, undefined symbols before runtime).
2. Boundary Invariants & Edge Cases (checks negative inputs, empty collections, nil checks).
3. Hygiene & Maintainability (flags removed docstrings, bare exceptions, hardcoded secrets, stray prints).
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rat.kernel.contracts import Artifact, ArtifactAction
from rat.kernel.registry import Capability, OperationDefinition


@dataclass
class ReviewFinding:
    file_path: str
    line_number: Optional[int]
    severity: str  # "CRITICAL" | "WARNING" | "SUGGESTION"
    lens: str      # "correctness" | "invariants" | "maintainability" | "security"
    title: str
    description: str
    suggested_fix: Optional[str] = None
    code_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[Tuple[str, int, str]] = field(default_factory=list)  # (type: '+', '-', ' ', line_no, content)


@dataclass
class DiffFile:
    old_path: str
    new_path: str
    status: str  # "modified" | "added" | "deleted"
    hunks: List[DiffHunk] = field(default_factory=list)
    added_lines: List[Tuple[int, str]] = field(default_factory=list)
    deleted_lines: List[Tuple[int, str]] = field(default_factory=list)

    @property
    def language(self) -> str:
        ext = Path(self.new_path or self.old_path).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".java": "java",
            ".json": "json",
            ".md": "markdown",
            ".yml": "yaml",
            ".yaml": "yaml",
        }
        return mapping.get(ext, "unknown")


# Regex pattern to match diff headers
_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_unified_diff(diff_text: str) -> List[DiffFile]:
    """Parse unified git diff output into structured DiffFile instances."""
    files: List[DiffFile] = []
    current_file: Optional[DiffFile] = None
    current_hunk: Optional[DiffHunk] = None
    new_line_idx = 0
    old_line_idx = 0

    for line in diff_text.splitlines():
        # Match file header: diff --git a/path b/path
        m_file = _DIFF_HEADER_RE.match(line)
        if m_file:
            old_p, new_p = m_file.group(1), m_file.group(2)
            current_file = DiffFile(
                old_path=old_p,
                new_path=new_p,
                status="modified",
            )
            files.append(current_file)
            current_hunk = None
            continue

        if not current_file:
            continue

        if line.startswith("new file mode"):
            current_file.status = "added"
            continue
        elif line.startswith("deleted file mode"):
            current_file.status = "deleted"
            continue

        # Match hunk header: @@ -old_start,old_count +new_start,new_count @@
        m_hunk = _HUNK_HEADER_RE.match(line)
        if m_hunk:
            old_start = int(m_hunk.group(1))
            old_count = int(m_hunk.group(2)) if m_hunk.group(2) else 1
            new_start = int(m_hunk.group(3))
            new_count = int(m_hunk.group(4)) if m_hunk.group(4) else 1

            current_hunk = DiffHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
            )
            current_file.hunks.append(current_hunk)
            new_line_idx = new_start
            old_line_idx = old_start
            continue

        if not current_hunk:
            continue

        if line.startswith("+"):
            content = line[1:]
            current_hunk.lines.append(("+", new_line_idx, content))
            current_file.added_lines.append((new_line_idx, content))
            new_line_idx += 1
        elif line.startswith("-"):
            content = line[1:]
            current_hunk.lines.append(("-", old_line_idx, content))
            current_file.deleted_lines.append((old_line_idx, content))
            old_line_idx += 1
        elif line.startswith(" ") or line == "":
            content = line[1:] if line.startswith(" ") else ""
            current_hunk.lines.append((" ", new_line_idx, content))
            new_line_idx += 1
            old_line_idx += 1

    return files


# Common standard library and popular external symbols that cause NameError if not imported
_COMMON_IMPORT_CHECKS = [
    (r"\bdeque\(", "deque", "from collections import deque"),
    (r"\bdefaultdict\(", "defaultdict", "from collections import defaultdict"),
    (r"\bCounter\(", "Counter", "from collections import Counter"),
    (r"\bOrderedDict\(", "OrderedDict", "from collections import OrderedDict"),
    (r"\bnamedtuple\(", "namedtuple", "from collections import namedtuple"),
    (r"\bre\.(search|match|findall|sub|split|finditer)\(", "re", "import re"),
    (r"\bjson\.(loads|dumps|load|dump)\(", "json", "import json"),
    (r"\bmath\.(sqrt|floor|ceil|pi|log|sin|cos|exp)\(", "math", "import math"),
    (r"\bos\.(path|environ|makedirs|listdir|remove|walk)\b", "os", "import os"),
    (r"\bsys\.(exit|argv|path|stdout|stderr)\b", "sys", "import sys"),
    (r"\btime\.(time|sleep|monotonic)\(", "time", "import time"),
    (r"\buuid4\(", "uuid4", "from uuid import uuid4"),
    (r"\bPath\(", "Path", "from pathlib import Path"),
]

# Sensitive patterns that might indicate leaked secrets
_SECRET_PATTERNS = [
    (re.compile(r"""(?:api_key|apikey|secret|token|password|auth_token)\s*=\s*['"][a-zA-Z0-9_\-]{16,}['"]""", re.IGNORECASE), "hardcoded credential or API secret"),
    (re.compile(r"""ghp_[a-zA-Z0-9]{36}"""), "GitHub Personal Access Token"),
    (re.compile(r"""sk-[a-zA-Z0-9]{32,}"""), "OpenAI / Cloud Secret Key"),
]


def analyze_diff_files(
    files: List[DiffFile],
    base_dir: Optional[str] = None
) -> List[ReviewFinding]:
    """Execute multi-lens code review checks across diff files."""
    findings: List[ReviewFinding] = []

    for file in files:
        if file.status == "deleted":
            continue

        # Full text of the file on disk if available (for import checks)
        disk_content: Optional[str] = None
        if base_dir:
            file_disk_path = Path(base_dir) / file.new_path
            if file_disk_path.is_file():
                try:
                    disk_content = file_disk_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    disk_content = None

        # -------------------------------------------------------------
        # Lens 1: Python Correctness & Missing Imports
        # -------------------------------------------------------------
        if file.language == "python":
            all_diff_text = "\n".join([c for _, c in file.added_lines])
            
            # Combine diff added text + disk text to know what's imported
            search_scope = (disk_content or "") + "\n" + all_diff_text

            for pattern, symbol, import_stmt in _COMMON_IMPORT_CHECKS:
                has_usage = any(re.search(pattern, content) for _, content in file.added_lines)
                if has_usage:
                    # Check if imported anywhere in disk_content or in diff
                    is_imported = bool(
                        re.search(rf"\bimport\s+{symbol}\b", search_scope) or
                        re.search(rf"\bfrom\s+[\w\.]+\s+import\s+.*\b{symbol}\b", search_scope)
                    )
                    if not is_imported:
                        # Find the first added line where it's used
                        line_num = None
                        snippet = None
                        for l_num, content in file.added_lines:
                            if re.search(pattern, content):
                                line_num = l_num
                                snippet = content.strip()
                                break

                        findings.append(ReviewFinding(
                            file_path=file.new_path,
                            line_number=line_num,
                            severity="CRITICAL",
                            lens="correctness",
                            title=f"Missing import: '{symbol}' used without import",
                            description=(
                                f"Identifier '{symbol}' is invoked in added code but is not imported. "
                                f"This will result in a runtime `NameError: name '{symbol}' is not defined`."
                            ),
                            suggested_fix=import_stmt,
                            code_snippet=snippet,
                        ))

        # -------------------------------------------------------------
        # Lens 2: Boundary Invariants & Edge Cases
        # -------------------------------------------------------------
        if file.language in ("python", "javascript", "typescript"):
            # Check for missing negative distance/depth checks
            for l_num, content in file.added_lines:
                # E.g. def node_query(..., distance: int) without distance < 0 validation
                if re.search(r"def\s+\w+\(.*\b(dist|distance|depth|hops|limit|count)\b.*:\s*int", content):
                    # Check if following lines validate negative values
                    has_check = any(
                        "< 0" in c or "<= 0" in c or "not isinstance" in c
                        for _, c in file.added_lines
                    )
                    if not has_check:
                        findings.append(ReviewFinding(
                            file_path=file.new_path,
                            line_number=l_num,
                            severity="WARNING",
                            lens="invariants",
                            title="Unchecked boundary: distance/depth parameter accepts negative values",
                            description=(
                                "Function accepts a distance or count parameter without validating whether it is negative. "
                                "Negative distance could cause unintended infinite exploration or empty results."
                            ),
                            suggested_fix="if distance < 0:\n    return []  # or raise ValueError('distance cannot be negative')",
                            code_snippet=content.strip(),
                        ))

            # Check for bare except: or pass in exception
            for l_num, content in file.added_lines:
                if re.search(r"^\s*except\s*:\s*$", content):
                    findings.append(ReviewFinding(
                        file_path=file.new_path,
                        line_number=l_num,
                        severity="WARNING",
                        lens="invariants",
                        title="Bare `except:` catches SystemExit and KeyboardInterrupt",
                        description=(
                            "Using a bare `except:` catches all exceptions including system interrupts. "
                            "Specify the expected exception type explicitly (e.g. `except Exception:`)."
                        ),
                        suggested_fix="except Exception as e:",
                        code_snippet=content.strip(),
                    ))

        # -------------------------------------------------------------
        # Lens 3: Hygiene & Maintainability
        # -------------------------------------------------------------
        # Check if docstrings were removed and not replaced
        deleted_docstrings = [c for _, c in file.deleted_lines if '"""' in c or "'''" in c]
        added_docstrings = [c for _, c in file.added_lines if '"""' in c or "'''" in c]
        if deleted_docstrings and not added_docstrings:
            findings.append(ReviewFinding(
                file_path=file.new_path,
                line_number=file.deleted_lines[0][0] if file.deleted_lines else None,
                severity="WARNING",
                lens="maintainability",
                title="Docstring removed from existing contract",
                description=(
                    "The diff deletes docstrings or documentation comments from the codebase without replacement. "
                    "Preserve public method documentation and parameter specifications."
                ),
                suggested_fix="Restore the function docstring with parameter and return descriptions.",
                code_snippet=deleted_docstrings[0].strip() if deleted_docstrings else None,
            ))

        # Check for stray debug prints
        is_test_file = "test" in file.new_path.lower() or "tests/" in file.new_path
        if not is_test_file and file.language == "python":
            for l_num, content in file.added_lines:
                if re.search(r"^\s*print\(", content) and not content.strip().startswith("#"):
                    findings.append(ReviewFinding(
                        file_path=file.new_path,
                        line_number=l_num,
                        severity="SUGGESTION",
                        lens="maintainability",
                        title="Stray `print()` statement in production module",
                        description=(
                            "Found raw `print()` call in non-test source code. "
                            "Use a structured logger (`logging` or rich console) or remove before merging."
                        ),
                        suggested_fix=None,
                        code_snippet=content.strip(),
                    ))

        # -------------------------------------------------------------
        # Lens 4: Security & Secrets
        # -------------------------------------------------------------
        if not is_test_file:
            for l_num, content in file.added_lines:
                for regex, label in _SECRET_PATTERNS:
                    if regex.search(content):
                        findings.append(ReviewFinding(
                            file_path=file.new_path,
                            line_number=l_num,
                            severity="CRITICAL",
                            lens="security",
                            title=f"Potential {label} committed to repository",
                            description=(
                                f"Line appears to contain a {label}. "
                                "Never commit credentials or tokens into source control. "
                                "Load from environment variables instead."
                            ),
                            suggested_fix="import os\napi_key = os.environ.get('API_KEY')",
                            code_snippet=content.strip()[:60] + "...",
                        ))
                        break

    return findings


def determine_verdict(findings: List[ReviewFinding]) -> Tuple[str, str]:
    """Calculate overall review verdict and explanation."""
    criticals = [f for f in findings if f.severity == "CRITICAL"]
    warnings = [f for f in findings if f.severity == "WARNING"]

    if criticals:
        verdict = "CHANGES_REQUESTED"
        summary = (
            f"⚠️ **Changes Requested**: Detected {len(criticals)} critical issue(s) "
            f"that will break runtime execution or compromise repository security."
        )
    elif warnings:
        verdict = "COMMENT_WITH_SUGGESTIONS"
        summary = (
            f"💬 **Comments & Recommendations**: Found {len(warnings)} boundary or hygiene improvement(s). "
            f"No critical runtime blockers detected."
        )
    else:
        verdict = "APPROVED"
        summary = "✅ **Approved**: Changes passed all automated correctness, invariant, and hygiene checks."

    return verdict, summary


def render_pr_review_markdown(
    target_name: str,
    verdict: str,
    verdict_summary: str,
    findings: List[ReviewFinding],
    total_files: int,
) -> str:
    """Format structured review findings into standard GitHub PR Markdown (SoL-Pi style)."""
    md = []
    md.append("## 🐀 RAT Automated Code Review")
    md.append("")
    md.append(f"**Target**: `{target_name}` | **Files Reviewed**: {total_files}")
    md.append(f"**Verdict**: **{verdict}**")
    md.append("")
    md.append(f"> {verdict_summary}")
    md.append("")

    criticals = [f for f in findings if f.severity == "CRITICAL"]
    warnings = [f for f in findings if f.severity == "WARNING"]
    suggestions = [f for f in findings if f.severity == "SUGGESTION"]

    if criticals:
        md.append("### 🚨 Critical Issues (Must Fix)")
        for f in criticals:
            loc = f"`{f.file_path}:{f.line_number}`" if f.line_number else f"`{f.file_path}`"
            md.append(f"- **{f.title}** ({loc})")
            md.append(f"  - **Impact**: {f.description}")
            if f.code_snippet:
                md.append(f"  - **Context**:\n    ```\n    {f.code_snippet}\n    ```")
            if f.suggested_fix:
                md.append(f"  - **Suggested Fix**:\n    ```python\n    {f.suggested_fix}\n    ```")
        md.append("")

    if warnings:
        md.append("### ⚠️ Boundary Invariants & Hygiene")
        for f in warnings:
            loc = f"`{f.file_path}:{f.line_number}`" if f.line_number else f"`{f.file_path}`"
            md.append(f"- **{f.title}** ({loc})")
            md.append(f"  - **Note**: {f.description}")
            if f.suggested_fix:
                md.append(f"  - **Recommendation**:\n    ```python\n    {f.suggested_fix}\n    ```")
        md.append("")

    if suggestions:
        md.append("### 💡 Suggestions")
        for f in suggestions:
            loc = f"`{f.file_path}:{f.line_number}`" if f.line_number else f"`{f.file_path}`"
            md.append(f"- **{f.title}** ({loc}): {f.description}")
        md.append("")

    if not findings:
        md.append("🎉 **Clean diff**: No missing imports, unhandled invariants, or docstring regressions found.")
        md.append("")

    md.append("---")
    md.append("*Generated by RAT (Reasoning Agent Toolkit) — Code Review Engine.*")
    return "\n".join(md)


def run_git_diff(repo_path: Optional[str] = None, staged: bool = False) -> str:
    """Fetch local diff using git command."""
    cmd = ["git"]
    if repo_path:
        cmd.extend(["-C", repo_path])
    cmd.append("diff")
    if staged:
        cmd.append("--cached")

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"git diff failed: {res.stderr.strip()}")
    return res.stdout


def run_gh_pr_diff(pr_target: str, repo: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """Fetch PR diff and metadata using gh CLI."""
    # First fetch metadata
    meta_cmd = ["gh", "pr", "view", pr_target, "--json", "title,body,author,baseRefName,headRefName,url,number"]
    if repo:
        meta_cmd.extend(["--repo", repo])

    meta_res = subprocess.run(meta_cmd, capture_output=True, text=True, check=False)
    if meta_res.returncode != 0:
        raise RuntimeError(f"gh pr view failed: {meta_res.stderr.strip()}")

    meta = json.loads(meta_res.stdout)

    # Now fetch unified diff
    diff_cmd = ["gh", "pr", "diff", pr_target]
    if repo:
        diff_cmd.extend(["--repo", repo])

    diff_res = subprocess.run(diff_cmd, capture_output=True, text=True, check=False)
    if diff_res.returncode != 0:
        raise RuntimeError(f"gh pr diff failed: {diff_res.stderr.strip()}")

    return diff_res.stdout, meta


def post_gh_pr_review(
    pr_target: str,
    comment_body: str,
    repo: Optional[str] = None,
    action: str = "COMMENT",  # "COMMENT" | "REQUEST_CHANGES" | "APPROVE"
) -> Dict[str, Any]:
    """Submit review to GitHub PR via gh CLI."""
    cmd = ["gh", "pr", "review", pr_target]
    if repo:
        cmd.extend(["--repo", repo])

    if action == "REQUEST_CHANGES":
        cmd.append("--request-changes")
    elif action == "APPROVE":
        cmd.append("--approve")
    else:
        cmd.append("--comment")

    cmd.extend(["-b", comment_body])

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"gh pr review failed: {res.stderr.strip()}")

    return {
        "status": "submitted",
        "action": action,
        "pr_target": pr_target,
        "repo": repo,
        "output": res.stdout.strip(),
    }


def observation_pack_formatter(res: Any) -> Any:
    """Format review result into compact SoL-Pi observation pack for prompt context."""
    if not isinstance(res, dict):
        return res
    return {
        "target": res.get("target"),
        "verdict": res.get("verdict"),
        "files_count": res.get("total_files", 0),
        "critical_count": len([f for f in res.get("findings", []) if f.get("severity") == "CRITICAL"]),
        "warning_count": len([f for f in res.get("findings", []) if f.get("severity") == "WARNING"]),
        "submitted": res.get("submitted", False),
    }


def create_code_review_capability(
    base_dir: Optional[str] = None,
) -> Capability:
    """Build and register the Code Review capability for RAT."""
    cap = Capability(
        name="code_review",
        title="Đánh giá mã nguồn (Code Review)",
        description="Phân tích diff git và GitHub PR qua các ống kính: tính đúng đắn (import), biên dữ liệu, và chất lượng mã.",
    )

    def handle_review_local_diff(args: Dict[str, Any], **context) -> Dict[str, Any]:
        staged = bool(args.get("staged", False))
        repo_path = args.get("repo_path") or base_dir or os.getcwd()
        diff_text = run_git_diff(repo_path=repo_path, staged=staged)

        if not diff_text.strip():
            return {
                "target": "local_working_tree" if not staged else "local_staged",
                "total_files": 0,
                "findings": [],
                "verdict": "APPROVED",
                "summary": "Không có thay đổi nào trong git diff.",
                "markdown": "## 🐀 RAT Code Review\n\nKhông phát hiện thay đổi nào trong git diff.",
            }

        files = parse_unified_diff(diff_text)
        findings = analyze_diff_files(files, base_dir=repo_path)
        verdict, summary = determine_verdict(findings)
        md = render_pr_review_markdown(
            target_name=f"local {'staged' if staged else 'unstaged'}",
            verdict=verdict,
            verdict_summary=summary,
            findings=findings,
            total_files=len(files),
        )

        return {
            "target": f"local_{'staged' if staged else 'unstaged'}",
            "repo_path": repo_path,
            "total_files": len(files),
            "findings": [f.to_dict() for f in findings],
            "verdict": verdict,
            "summary": summary,
            "markdown": md,
        }

    def handle_review_github_pr(args: Dict[str, Any], **context) -> Dict[str, Any]:
        pr_target = str(args.get("pr_target", "")).strip()
        if not pr_target:
            raise ValueError("pr_target (số PR hoặc URL) là bắt buộc.")
        repo = args.get("repo")
        submit = bool(args.get("submit", False))

        diff_text, meta = run_gh_pr_diff(pr_target=pr_target, repo=repo)
        files = parse_unified_diff(diff_text)
        findings = analyze_diff_files(files, base_dir=None)
        verdict, summary = determine_verdict(findings)

        target_title = f"#{meta.get('number', pr_target)}: {meta.get('title', '')}"
        md = render_pr_review_markdown(
            target_name=target_title,
            verdict=verdict,
            verdict_summary=summary,
            findings=findings,
            total_files=len(files),
        )

        submitted_info = None
        if submit:
            action = "REQUEST_CHANGES" if verdict == "CHANGES_REQUESTED" else "COMMENT"
            submitted_info = post_gh_pr_review(pr_target=pr_target, comment_body=md, repo=repo, action=action)

        return {
            "target": target_title,
            "pr_target": pr_target,
            "pr_url": meta.get("url"),
            "author": meta.get("author", {}).get("login"),
            "total_files": len(files),
            "findings": [f.to_dict() for f in findings],
            "verdict": verdict,
            "summary": summary,
            "markdown": md,
            "submitted": submit,
            "submission_details": submitted_info,
        }

    cap.register_operation(OperationDefinition(
        name="review_local_diff",
        description="Inspect local working directory diff or staged changes for defects, missing imports, and invariants.",
        parameters={
            "type": "object",
            "properties": {
                "staged": {"type": "boolean", "description": "Review staged changes (--cached) instead of unstaged diff."},
                "repo_path": {"type": "string", "description": "Path to local git repository."},
            },
        },
        handler=handle_review_local_diff,
        artifact_kind="code_review",
        observation_formatter=observation_pack_formatter,
    ))

    cap.register_operation(OperationDefinition(
        name="review_github_pr",
        description="Fetch, analyze, and optionally submit a multi-lens review for an open GitHub Pull Request.",
        parameters={
            "type": "object",
            "required": ["pr_target"],
            "properties": {
                "pr_target": {"type": "string", "description": "PR number (e.g. '5') or URL."},
                "repo": {"type": "string", "description": "GitHub repository 'owner/repo' if not inferred from directory."},
                "submit": {"type": "boolean", "description": "Submit formatted review back to GitHub PR via gh CLI."},
            },
        },
        handler=handle_review_github_pr,
        artifact_kind="code_review",
        observation_formatter=observation_pack_formatter,
    ))

    return cap
