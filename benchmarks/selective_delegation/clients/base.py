"""Base interface for cloud reasoning clients."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CloudModelClient(ABC):
    """Normalized interface for frontier cloud reasoning models."""

    provider: str = "base"

    @abstractmethod
    def chat_with_meta(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """
        Execute completion and return normalized metadata:
        {
            "content": str,
            "provider": str,
            "model": str,
            "input_tokens": int | None,
            "output_tokens": int | None,
            "latency_seconds": float,
            "cost_usd": float | None,
            "error": str | None,
        }
        """
        raise NotImplementedError
