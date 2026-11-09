"""Download and normalize GSM8K JSONL without modifying the source dataset."""
from __future__ import annotations

import hashlib
import json
import random
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl"


def download_gsm8k(destination: Path, url: str = DEFAULT_URL, timeout: int = 30) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "CHUOT-Research-Benchmark/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    destination.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def load_gsm8k(path: Path, limit: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if not line.strip():
                continue
            item = json.loads(line)
            answer = item["answer"].rsplit("####", 1)[-1].strip().replace(",", "")
            try:
                numeric_answer = float(answer)
            except ValueError as exc:
                raise ValueError(f"GSM8K row {index} has an unparseable target: {answer!r}") from exc
            rows.append({
                "task_id": f"gsm8k_test_{index:04d}",
                "dataset": "gsm8k",
                "split": "test",
                "question": item["question"].strip(),
                "ground_truth": answer,
                "ground_truth_numeric": numeric_answer,
                "source_index": index,
            })
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if limit >= len(rows):
        return rows
    # Deterministic sample; source indices are retained in the output for auditability.
    selected = random.Random(seed).sample(rows, limit)
    return sorted(selected, key=lambda row: row["source_index"])
