"""B0: one local model attempt, no verifier repair and no cloud escalation."""
from __future__ import annotations
import re
import time
from typing import Any

SYSTEM_PROMPT = (
    "Solve the math word problem carefully. Give a concise explanation, then put the final "
    "numeric answer on the last line exactly as: #### number. Do not omit the final line."
)


def extract_numeric_answer(text: str) -> str | None:
    if not text:
        return None
    matches = re.findall(r"####\\s*([-+]?(?:\\d[\\d,]*\\.?\\d*|\\.\\d+))", text)
    if matches:
        return matches[-1].replace(",", "")
    # Fallback is intentionally conservative: use the last standalone numeric token.
    matches = re.findall(r"(?<![\\w.])[-+]?(?:\\d[\\d,]*\\.?\\d*|\\.\\d+)(?![\\w.])", text)
    return matches[-1].replace(",", "") if matches else None


class LocalOnlyStrategy:
    name = "local_only"

    def __init__(self, client: Any, max_tokens: int = 1024, timeout: float = 180.0):
        self.client = client
        self.max_tokens = max_tokens
        self.timeout = timeout

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["question"]},
        ]
        started = time.perf_counter()
        response = self.client.chat_with_meta(
            messages, tools=[], timeout=self.timeout, max_tokens=self.max_tokens,
            thinking=False,
        )
        elapsed = time.perf_counter() - started
        message = response.get("message") or {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        return {
            "final_answer": content,
            "predicted_numeric": extract_numeric_answer(content),
            "error": response.get("error"),
            "local_tokens": (response.get("prompt_tokens", 0) or 0) + (response.get("completion_tokens", 0) or 0),
            "prompt_tokens": response.get("prompt_tokens"),
            "completion_tokens": response.get("completion_tokens"),
            "token_usage_known": bool(response.get("token_usage_known", False)),
            "latency_seconds": elapsed,
            "cloud_calls": 0,
            "cloud_cost_usd": 0.0,
            "verification_status": "NOT_RUN",
            "repair_attempts": 0,
        }
