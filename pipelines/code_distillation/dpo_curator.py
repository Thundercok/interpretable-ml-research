"""Protocol II: Contrastive Preference Dataset (DPO/SFT) Curator for Code Distillation.

Generates standard DPO triples (prompt, chosen, rejected) where:
- chosen (y_w): Precise root cause, state corruption vector, and minimal patch in Senior Peer Tone.
- rejected (y_l): Superficial style/naming nitpicks or hallucinated errors (AI slop).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_DPO_PATH = Path("data/distillation/code_review_dpo.jsonl")


@dataclass
class DPOContrastivePair:
    id: str
    source_repo: str
    pr_number: int
    category: str  # "CONCURRENCY_OR_MEMORY" | "SECURITY_BOUNDARY" | "ALGORITHMIC_COMPLEXITY"
    prompt: str
    teacher_cot: str
    chosen: str  # y_w: Precise defect & minimal patch (Sniper tone)
    rejected: str  # y_l: Stylistic fluff / missed bug (AI slop)
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DPOCurator:
    def __init__(self, output_path: Path | str = DEFAULT_DPO_PATH):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def append_pair(self, pair: DPOContrastivePair) -> None:
        with open(self.output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(pair.to_dict(), ensure_ascii=False) + "\n")

    def count(self) -> int:
        if not self.output_path.exists():
            return 0
        with open(self.output_path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def read_all(self) -> list[dict[str, Any]]:
        if not self.output_path.exists():
            return []
        with open(self.output_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
