"""Google Gemini Cloud Client for Selective Delegation Benchmark."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from benchmarks.selective_delegation.clients.base import CloudModelClient

logger = logging.getLogger("benchmarks.clients.gemini")

# Pricing per million tokens (USD)
GEMINI_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
}
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiClient(CloudModelClient):
    provider = "gemini"

    def __init__(self, api_key: str | None = None, default_model: str = DEFAULT_GEMINI_MODEL):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required to instantiate GeminiClient.")
        self.default_model = default_model

    def _calculate_cost(self, model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if input_tokens is None or output_tokens is None:
            return None
        # Match prefix in pricing dict if exact not found
        rates = None
        for key, rate in GEMINI_PRICING.items():
            if key in model.lower():
                rates = rate
                break
        if rates is None:
            rates = GEMINI_PRICING["gemini-2.5-flash"]
        cost = (input_tokens / 1_000_000 * rates["input"]) + (output_tokens / 1_000_000 * rates["output"])
        return round(cost, 8)

    def chat_with_meta(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        target_model = model or self.default_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={self.api_key}"

        # Convert chat messages to Gemini contents format
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            elif role in ("user", "human"):
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role in ("assistant", "model"):
                contents.append({"role": "model", "parts": [{"text": content}]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                latency = time.perf_counter() - started
                result = json.loads(response.read().decode("utf-8"))

            candidates = result.get("candidates", [])
            content_text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                content_text = "".join(part.get("text", "") for part in parts).strip()

            usage = result.get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount")
            output_tokens = usage.get("candidatesTokenCount")
            cost_usd = self._calculate_cost(target_model, input_tokens, output_tokens)

            return {
                "content": content_text,
                "provider": self.provider,
                "model": target_model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_seconds": latency,
                "cost_usd": cost_usd,
                "error": None,
            }
        except urllib.error.HTTPError as exc:
            latency = time.perf_counter() - started
            err_body = exc.read().decode("utf-8", errors="replace")
            logger.error(f"Gemini API HTTPError {exc.code}: {err_body}")
            return {
                "content": "",
                "provider": self.provider,
                "model": target_model,
                "input_tokens": None,
                "output_tokens": None,
                "latency_seconds": latency,
                "cost_usd": None,
                "error": f"HTTPError {exc.code}: {err_body[:200]}",
            }
        except Exception as exc:
            latency = time.perf_counter() - started
            logger.error(f"Gemini API unexpected error: {exc}")
            return {
                "content": "",
                "provider": self.provider,
                "model": target_model,
                "input_tokens": None,
                "output_tokens": None,
                "latency_seconds": latency,
                "cost_usd": None,
                "error": str(exc),
            }
