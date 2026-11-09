"""Comprehensive unit tests for all strategies B0 - B5."""
import pytest
from benchmarks.selective_delegation.strategies.local_retry import LocalRetryStrategy
from benchmarks.selective_delegation.strategies.verified_repair import VerifiedRepairStrategy
from benchmarks.selective_delegation.strategies.always_cloud import AlwaysCloudStrategy
from benchmarks.selective_delegation.strategies.static_escalation import StaticEscalationStrategy
from benchmarks.selective_delegation.strategies.selective import SelectiveStrategy, SelectiveDelegationPolicy


class MockLocalClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    def chat_with_meta(self, messages, tools=None, **kwargs):
        self.call_count += 1
        content = self.responses.pop(0) if self.responses else "#### 0"
        return {
            "message": {"content": content},
            "prompt_tokens": 15,
            "completion_tokens": 10,
            "token_usage_known": True,
            "error": None,
        }


class MockCloudClient:
    def __init__(self, response="Solution...\n#### 42", cost=0.001):
        self.response = response
        self.cost = cost
        self.call_count = 0

    def chat_with_meta(self, messages, **kwargs):
        self.call_count += 1
        return {
            "content": self.response,
            "provider": "mock_cloud",
            "model": "mock-model",
            "input_tokens": 50,
            "output_tokens": 20,
            "latency_seconds": 0.5,
            "cost_usd": self.cost,
            "error": None,
        }


def test_b1_local_retry():
    # Response 1: missing answer (FAIL) -> Retries -> Response 2: correct (PASS)
    client = MockLocalClient(["Thinking without answer", "4 + 4 = 8\n#### 8"])
    strat = LocalRetryStrategy(client)
    res = strat.run({"question": "What is 4 + 4?"})

    assert res["predicted_numeric"] == "8"
    assert res["repair_attempts"] == 1
    assert client.call_count == 2
    assert res["cloud_calls"] == 0


def test_b2_verified_repair():
    # Response 1: arithmetic error 2 + 2 = 5 -> Feedback -> Response 2: 2 + 2 = 4 -> PASS
    client = MockLocalClient(["2 + 2 = 5\n#### 5", "2 + 2 = 4\n#### 4"])
    strat = VerifiedRepairStrategy(client, max_repairs=2)
    res = strat.run({"question": "What is 2 + 2?"})

    assert res["predicted_numeric"] == "4"
    assert res["verification_status"] == "PASS"
    assert res["repair_attempts"] == 1
    assert client.call_count == 2
    assert res["cloud_calls"] == 0


def test_b3_always_cloud():
    cloud = MockCloudClient("4 * 5 = 20\n#### 20", cost=0.0005)
    strat = AlwaysCloudStrategy(cloud)
    res = strat.run({"question": "What is 4 * 5?"})

    assert res["predicted_numeric"] == "20"
    assert res["cloud_calls"] == 1
    assert res["cloud_cost_usd"] == 0.0005
    assert res["local_tokens"] == 0
    assert cloud.call_count == 1


def test_b4_static_escalation_accept_on_pass():
    local = MockLocalClient(["10 + 10 = 20\n#### 20"])
    cloud = MockCloudClient()
    strat = StaticEscalationStrategy(local, cloud)
    res = strat.run({"question": "What is 10 + 10?"})

    assert res["predicted_numeric"] == "20"
    assert res["cloud_calls"] == 0
    assert not res["escalated"]
    assert cloud.call_count == 0


def test_b4_static_escalation_delegates_on_fail():
    local = MockLocalClient(["10 + 10 = 25\n#### 25"])  # arithmetic fail
    cloud = MockCloudClient("10 + 10 = 20\n#### 20")
    strat = StaticEscalationStrategy(local, cloud)
    res = strat.run({"question": "What is 10 + 10?"})

    assert res["predicted_numeric"] == "20"
    assert res["cloud_calls"] == 1
    assert res["escalated"]
    assert cloud.call_count == 1


def test_b5_selective_repairs_arithmetic_first_then_accepts():
    # Local attempt 1 has arithmetic error -> Policy decides REPAIR_LOCAL -> Attempt 2 fixes it -> ACCEPT
    local = MockLocalClient(["3 * 3 = 8\n#### 8", "3 * 3 = 9\n#### 9"])
    cloud = MockCloudClient()
    strat = SelectiveStrategy(local, cloud)
    res = strat.run({"question": "What is 3 * 3?"})

    assert res["predicted_numeric"] == "9"
    assert res["cloud_calls"] == 0
    assert res["repair_attempts"] == 1
    assert cloud.call_count == 0
    assert any(step["action"] == "REPAIR_LOCAL" for step in res["decision_trace"])
    assert any(step["action"] == "ACCEPT" for step in res["decision_trace"])


def test_b5_selective_delegates_when_repairs_exhausted():
    # Local keeps failing -> repairs exhausted -> DELEGATE
    local = MockLocalClient(["3 * 3 = 7\n#### 7", "3 * 3 = 8\n#### 8", "3 * 3 = 10\n#### 10"])
    cloud = MockCloudClient("3 * 3 = 9\n#### 9")
    strat = SelectiveStrategy(local, cloud, max_repairs=2)
    res = strat.run({"question": "What is 3 * 3?"})

    assert res["predicted_numeric"] == "9"
    assert res["cloud_calls"] == 1
    assert cloud.call_count == 1
    assert any(step["action"] == "DELEGATE" for step in res["decision_trace"])
