"""Protocol I: Deterministic Hazard & Entropy Gate for Public Code Diffs.

Filters out noise (docs, formatting, lockfiles) and calculates a risk score R(d_i).
Diffs are only admitted to frontier audit if R(d_i) >= 4.5.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# File extensions allowed for systems & security review
ALLOWED_EXTENSIONS = {".py", ".rs", ".go", ".cpp", ".cc", ".cxx", ".cs", ".c", ".h", ".hpp"}

# File patterns that are discarded immediately as noise
NOISE_PATTERNS = [
    r"\.md$",
    r"\.rst$",
    r"\.txt$",
    r"\.json$",
    r"\.ya?ml$",
    r"\.toml$",
    r"lock\b",
    r"\.lock$",
    r"\.css$",
    r"\.scss$",
    r"\.svg$",
    r"\.png$",
    r"\.jpe?g$",
    r"(^|/)docs?/",
    r"(^|/)\.github/",
    r"(^|/)tests?/",
    r"(^|/)fixtures?/",
]

# Hazard pattern rules with associated risk weights
HAZARD_RULES: list[tuple[str, re.Pattern, float]] = [
    # Concurrency and Async Hazards
    ("concurrency_lock", re.compile(r"\b(Lock|lock|Mutex|mutex|RwLock|Semaphore|synchronized|Atomic\w*)\b"), 2.5),
    ("async_unawaited", re.compile(r"\b(async\s+def|await\b|asyncio\.create_task|go\s+\w+|tokio::spawn)"), 2.5),
    ("goroutine_channel", re.compile(r"(<-chan|\bchan\s+\w+|select\s*\{)"), 2.5),

    # Security & Injection Sinks
    ("sql_injection_sink", re.compile(r"\b(execute|cursor|query)\s*\(\s*f?[\"'].*?(%s|\{|\+)", re.IGNORECASE), 3.0),
    ("subprocess_injection", re.compile(r"\b(os\.system|subprocess\.Popen|subprocess\.run|exec\(|eval\()"), 3.0),
    ("path_traversal", re.compile(r"\b(open|read_file|Path)\s*\(.*?(\+|\.format|f[\"']).*?\b(path|filename|file_name)", re.IGNORECASE), 2.5),

    # Memory Safety & Unsafe Casts
    ("unsafe_block", re.compile(r"\b(unsafe\s*\{|reinterpret_cast|static_cast<|Marshal\.)"), 3.0),
    ("raw_pointer_alloc", re.compile(r"\b(malloc|free|calloc|realloc|new\s+\w+\[)"), 2.5),

    # Algorithmic Complexity / Blocking I/O
    ("nested_loops", re.compile(r"(for\b.*?\n.*?for\b|while\b.*?\n.*?while\b)", re.DOTALL), 2.0),
    ("blocking_in_async", re.compile(r"(async\s+def\b.*?\b(time\.sleep|requests\.get|urllib\.request|open\())", re.DOTALL), 3.0),

    # Error Suppression & Silent Failures
    ("silent_swallow", re.compile(r"(except\s*:\s*pass|catch\s*\([^\)]*\)\s*\{\s*\})"), 2.0),
    ("raw_panic_unwrap", re.compile(r"\.(unwrap|expect)\s*\("), 1.5),
]


@dataclass
class DiffHunk:
    file_path: str
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    raw_hunk: str = ""


@dataclass
class HazardGateResult:
    is_noise: bool
    risk_score: float
    admitted: bool
    detected_hazards: list[str]
    target_files: list[str]
    rejection_reason: str | None = None


def parse_unified_diff(raw_diff: str) -> list[DiffHunk]:
    """Extracts per-file hunks and added code lines from a git unified diff."""
    hunks: list[DiffHunk] = []
    current_file = ""
    current_hunk = DiffHunk(file_path="")

    for line in raw_diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if line.startswith("diff --git"):
            if current_hunk.file_path and (current_hunk.added_lines or current_hunk.removed_lines):
                hunks.append(current_hunk)
            current_hunk = DiffHunk(file_path=current_file)
            continue
        if line.startswith("+") and not line.startswith("+++"):
            current_hunk.file_path = current_file
            current_hunk.added_lines.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            current_hunk.file_path = current_file
            current_hunk.removed_lines.append(line[1:])

    if current_hunk.file_path and (current_hunk.added_lines or current_hunk.removed_lines):
        hunks.append(current_hunk)

    return hunks


def evaluate_diff_hazard(raw_diff: str, threshold: float = 4.5) -> HazardGateResult:
    """Evaluates a raw unified diff against Protocol I hazard and noise filters."""
    hunks = parse_unified_diff(raw_diff)

    if not hunks:
        return HazardGateResult(
            is_noise=True,
            risk_score=0.0,
            admitted=False,
            detected_hazards=[],
            target_files=[],
            rejection_reason="Empty diff or no hunks extracted",
        )

    # 1. Filter out non-target files and noise
    valid_files: list[str] = []
    has_target_language = False

    for hunk in hunks:
        path = hunk.file_path
        # Check noise patterns
        is_noisy = any(re.search(pat, path, re.IGNORECASE) for pat in NOISE_PATTERNS)
        ext = Path(path).suffix.lower()

        if is_noisy:
            continue
        if ext in ALLOWED_EXTENSIONS:
            has_target_language = True
            valid_files.append(path)

    if not has_target_language:
        return HazardGateResult(
            is_noise=True,
            risk_score=0.0,
            admitted=False,
            detected_hazards=[],
            target_files=valid_files,
            rejection_reason="Noise suppression: No code changes in target languages (.py, .rs, .go, .cpp, .cs)",
        )

    # 2. Extract aggregated modified code across target files (both added and removed)
    target_modified_code: list[str] = []
    for hunk in hunks:
        if hunk.file_path in valid_files:
            target_modified_code.extend(hunk.added_lines)
            target_modified_code.extend(hunk.removed_lines)

    code_text = "\n".join(target_modified_code)
    if not code_text.strip():
        return HazardGateResult(
            is_noise=True,
            risk_score=0.0,
            admitted=False,
            detected_hazards=[],
            target_files=valid_files,
            rejection_reason="No substantive modified code lines",
        )

    # 3. Calculate lexical & AST hazard risk score R(d_i)
    total_score = 0.0
    detected_hazards: list[str] = []

    for name, pattern, weight in HAZARD_RULES:
        matches = pattern.findall(code_text)
        if matches:
            total_score += weight
            detected_hazards.append(f"{name} (+{weight})")

    admitted = total_score >= threshold
    rejection_reason = None if admitted else f"Hazard score {total_score:.1f} < threshold {threshold}"

    return HazardGateResult(
        is_noise=False,
        risk_score=round(total_score, 2),
        admitted=admitted,
        detected_hazards=detected_hazards,
        target_files=valid_files,
        rejection_reason=rejection_reason,
    )
