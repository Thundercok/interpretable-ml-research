# Backlog: Systems & Security Code-Review Sniper & Knowledge Distillation

**Date Recorded**: 2026-11-09  
**Status**: Deferred to future session (Live external posting paused; core gating & DPO pipeline active)

---

## 1. System Objective
A dual-purpose resident agent:
1. **Live Sniper Review**: Audits open GitHub PRs for critical concurrency, memory safety, and security vulnerabilities with zero noise/style nitpicks.
2. **Shadow Distillation Engine**: Curates high-precision contrastive preference datasets (SFT / DPO JSONL) from real PR audits to fine-tune local open-weights student models (Qwen-Coder / DeepSeek-Coder via MLX / TRL).

---

## 2. Implemented Components (2026-11-09)
- **`pipelines/code_distillation/hazard_gate.py`**:
  - Deterministic AST & lexical hazard gate.
  - Automatically suppresses documentation, lockfiles, CI configs, asset updates, and test suites.
  - Calculates hazard score $R(d_i)$ across concurrency locks, async coroutines, raw SQL sinks, subprocess calls, unsafe pointers, and nested loops.
  - Gate threshold: $R(d_i) \ge 4.5$.
- **`pipelines/code_distillation/dpo_curator.py`**:
  - Manages contrastive DPO JSONL records (`prompt`, `teacher_cot`, `chosen`, `rejected`, `metadata`).
  - Formats `chosen` ($y_w$) in senior peer tone (exact defect root cause, state corruption vector, minimal patch).
  - Formats `rejected` ($y_l$) as superficial AI slop (formatting/naming nitpicks that miss the core bug).
- **`data/distillation/code_review_dpo.jsonl`**:
  - Seeded with verified real-world PR extraction from `redis/redis-py#4509`.
- **Test Suite**:
  - 29 unit tests passing across benchmark strategies, ExperienceBank, and code distillation pipeline.

---

## 3. Next Session Roadmap (Live Stream & Human Gate)
1. **Live Open PR Ingestion Stream**:
   - Query GitHub API for *open* PRs with $R(d_i) \ge 4.5$ across mid-sized systems repos (150–2,500 stars).
   - Target languages: `.py`, `.rs`, `.go`, `.cpp`, `.cs`.
2. **Automated Sandbox Repro Runner**:
   - Execute proposed reproduction scripts in a sandbox to confirm deterministic failure before surfacing to human review.
3. **Interactive Human Approval Gate**:
   - Surface candidate review card to user:
     - Target PR & diff lines.
     - Terminal output of failing reproduction test.
     - Minimal proposed patch.
   - User command required (`approve` / `edit` / `drop`) before any GitHub emission.
