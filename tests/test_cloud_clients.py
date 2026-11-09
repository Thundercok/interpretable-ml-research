"""Unit tests for CloudModelClient implementations and factory."""
import json
from unittest.mock import MagicMock, patch
import pytest

from benchmarks.selective_delegation.clients.factory import get_cloud_client
from benchmarks.selective_delegation.clients.gemini import GeminiClient
from benchmarks.selective_delegation.clients.anthropic import AnthropicClient


def test_factory_missing_api_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_cloud_client("gemini")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        get_cloud_client("anthropic")


def test_factory_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported cloud provider"):
        get_cloud_client("unknown_provider", api_key="dummy")


def test_gemini_client_mock_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client = get_cloud_client("gemini", model="gemini-2.5-flash")

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "candidates": [{
            "content": {"parts": [{"text": "Solution step...\n#### 42"}]}
        }],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 50,
        }
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        res = client.chat_with_meta([{"role": "user", "content": "What is 6 * 7?"}])

    assert res["content"] == "Solution step...\n#### 42"
    assert res["provider"] == "gemini"
    assert res["model"] == "gemini-2.5-flash"
    assert res["input_tokens"] == 100
    assert res["output_tokens"] == 50
    assert res["cost_usd"] is not None and res["cost_usd"] > 0
    assert res["error"] is None


def test_anthropic_client_mock_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = get_cloud_client("anthropic", model="claude-3-5-sonnet-latest")

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "content": [{"type": "text", "text": "Solution step...\n#### 42"}],
        "usage": {
            "input_tokens": 80,
            "output_tokens": 40,
        }
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        res = client.chat_with_meta([{"role": "user", "content": "What is 6 * 7?"}])

    assert res["content"] == "Solution step...\n#### 42"
    assert res["provider"] == "anthropic"
    assert res["input_tokens"] == 80
    assert res["output_tokens"] == 40
    assert res["cost_usd"] is not None and res["cost_usd"] > 0
    assert res["error"] is None
