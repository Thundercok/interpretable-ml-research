"""Anthropic Claude Cloud Client for Selective Delegation Benchmark."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from benchmarks.selective_delegation.clients.base import CloudModelClient

logger = logging.getLogger("benchmarks.clients.anthropic")

# Pricing per million tokens (USD)
ANTHROPIC_PRICING: dict[str, dict[str, float]] = {
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-7-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
}
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"


class AnthropicClient(CloudModelClient):
    provider = "anthropic"

    def __init__(self, api_key: str | None = None, default_model: str = DEFAULT_ANTHROPIC_MODEL):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required to instantiate AnthropicClient.")
        self.default_model = default_model

    def _calculate_cost(self, model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if input_tokens is None or output_tokens is None:
            return None
        rates = None
        for key, rate in ANTHROPIC_PRICING.items():
            if key in model.lower():
                rates = rate
                break
        if rates is None:
            rates = ANTHROPIC_PRICING["claude-3-5-sonnet"]
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
        url = "https://api.anthropic.com/v1/messages"

        system_prompt = None
        formatted_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role in ("user", "human"):
                formatted_messages.append({"role": "user", "content": content})
            elif role in ("assistant", "model"):
                formatted_messages.append({"role": "assistant", "content": content})

        payload: dict[str, Any] = {
            "model": target_model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                latency = time.perf_counter() - started
                result = json.loads(response.read().decode("utf-8"))

            content_text = ""
            for block in result.get("content", []):
                if block.get("type") == "text":
                    content_text += block.get("text", "")
            content_text = content_text.strip()

            usage = result.get("usage", {})
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
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
            logger.error(f"Anthropic API HTTPError {exc.code}: {err_body}")
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
            logger.error(f"Anthropic API unexpected error: {exc}")
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
