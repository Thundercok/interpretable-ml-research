"""Factory for creating plug-and-play cloud reasoning clients."""
from __future__ import annotations

import os
from benchmarks.selective_delegation.clients.base import CloudModelClient
from benchmarks.selective_delegation.clients.gemini import GeminiClient, DEFAULT_GEMINI_MODEL
from benchmarks.selective_delegation.clients.anthropic import AnthropicClient, DEFAULT_ANTHROPIC_MODEL


def get_cloud_client(
    provider: str = "gemini",
    model: str | None = None,
    api_key: str | None = None,
) -> CloudModelClient:
    """Return configured cloud model client based on provider."""
    normalized_provider = provider.strip().lower()
    if normalized_provider == "gemini":
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set in environment. Set GEMINI_API_KEY before running cloud benchmarks."
            )
        return GeminiClient(api_key=key, default_model=model or DEFAULT_GEMINI_MODEL)

    if normalized_provider in ("anthropic", "claude"):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set in environment. Set ANTHROPIC_API_KEY before running cloud benchmarks."
            )
        return AnthropicClient(api_key=key, default_model=model or DEFAULT_ANTHROPIC_MODEL)

    raise ValueError(f"Unsupported cloud provider: {provider!r}. Choose 'gemini' or 'anthropic'.")
