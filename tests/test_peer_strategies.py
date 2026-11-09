"""Unit tests for peer baseline strategies: FrugalGPT and AutoMix."""
import pytest
from benchmarks.selective_delegation.strategies.frugalgpt import FrugalGPTStrategy
from benchmarks.selective_delegation.strategies.automix import AutoMixStrategy


class MockLocalClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    def chat_with_meta(self, messages, tools=None, **kwargs):
        self.call_count += 1
        content = self.responses.pop(0) if self.responses else "#### 0"
        return {
            "message": {"content": content},
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "token_usage_known": True,
            "error": None,
        }


class MockCloudClient:
    def __init__(self, response="Cloud solution...\n#### 42", cost=0.001):
        self.response = response
        self.cost = cost
        self.call_count = 0

    def chat_with_meta(self, messages, **kwargs):
        self.call_count += 1
        return {
            "content": self.response,
            "provider": "mock_cloud",
            "model": "mock-frontier",
            "input_tokens": 60,
            "output_tokens": 25,
            "latency_seconds": 0.4,
            "cost_usd": self.cost,
            "error": None,
        }


def test_frugalgpt_accepts_when_majority_agrees():
    # 3 samples: 2 say 15, 1 says 12 -> Majority 15 (agreement 2/3 = 0.67 >= 0.67)
    local = MockLocalClient([
        "Path 1: 10 + 5 = 15\n#### 15",
        "Path 2: 10 + 2 = 12\n#### 12",
        "Path 3: 10 + 5 = 15\n#### 15",
    ])
    cloud = MockCloudClient()
    strat = FrugalGPTStrategy(local, cloud, k=3, threshold=0.66)
    res = strat.run({"question": "What is 10 + 5?"})

    assert res["predicted_numeric"] == "15"
    assert res["cloud_calls"] == 0
    assert not res["escalated"]
    assert local.call_count == 3
    assert cloud.call_count == 0
    assert res["confidence_score"] >= 0.66


def test_frugalgpt_cascades_when_consensus_is_low():
    # 3 samples: 3 different answers -> agreement 1/3 = 0.33 < 0.67 -> cascade
    local = MockLocalClient([
        "Path 1: 10 + 5 = 11\n#### 11",
        "Path 2: 10 + 5 = 12\n#### 12",
        "Path 3: 10 + 5 = 13\n#### 13",
    ])
    cloud = MockCloudClient("Calculated carefully: 10 + 5 = 15\n#### 15", cost=0.002)
    strat = FrugalGPTStrategy(local, cloud, k=3, threshold=0.66)
    res = strat.run({"question": "What is 10 + 5?"})

    assert res["predicted_numeric"] == "15"
    assert res["cloud_calls"] == 1
    assert res["escalated"]
    assert local.call_count == 3
    assert cloud.call_count == 1
    assert res["cloud_cost_usd"] == 0.002


def test_automix_accepts_on_meta_verifier_pass():
    # Call 1: generator produces solution
    # Call 2: meta-verifier confirms correctness with VERIFICATION: PASS
    local = MockLocalClient([
        "Step 1: 7 * 8 = 56\n#### 56",
        "The multiplication is correct.\nVERIFICATION: PASS",
    ])
    cloud = MockCloudClient()
    strat = AutoMixStrategy(local, cloud)
    res = strat.run({"question": "What is 7 * 8?"})

    assert res["predicted_numeric"] == "56"
    assert res["cloud_calls"] == 0
    assert not res["escalated"]
    assert res["meta_verifier_decision"] == "PASS"
    assert local.call_count == 2
    assert cloud.call_count == 0


def test_automix_escalates_on_meta_verifier_fail():
    # Call 1: generator produces faulty solution
    # Call 2: meta-verifier spots error and outputs VERIFICATION: FAIL
    local = MockLocalClient([
        "Step 1: 7 * 8 = 54\n#### 54",
        "Error in step 1: 7 * 8 = 56, not 54.\nVERIFICATION: FAIL",
    ])
    cloud = MockCloudClient("Step 1: 7 * 8 = 56\n#### 56", cost=0.0015)
    strat = AutoMixStrategy(local, cloud)
    res = strat.run({"question": "What is 7 * 8?"})

    assert res["predicted_numeric"] == "56"
    assert res["cloud_calls"] == 1
    assert res["escalated"]
    assert res["meta_verifier_decision"] == "FAIL"
    assert "Error in step 1" in res["meta_verifier_feedback"]
    assert local.call_count == 2
    assert cloud.call_count == 1


from benchmarks.selective_delegation.strategies.peer_review import LocalPeerReviewStrategy


def test_peer_review_accepts_immediate_pass():
    local = MockLocalClient(["4 + 4 = 8\n#### 8"])
    cloud = MockCloudClient()
    strat = LocalPeerReviewStrategy(local, cloud)
    res = strat.run({"question": "What is 4 + 4?"})

    assert res["predicted_numeric"] == "8"
    assert res["cloud_calls"] == 0
    assert not res["escalated"]
    assert res["peer_revisions"] == 0
    assert local.call_count == 1
    assert cloud.call_count == 0


def test_peer_review_revises_and_saves_escalation():
    # Call 1: Proposer makes arithmetic mistake
    # Call 2: Critic points out the exact mistake with REVIEW: REVISE
    # Call 3: Proposer revises based on critique and fixes it
    local = MockLocalClient([
        "2 + 2 = 5\n#### 5",
        "Arithmetic error: 2 + 2 = 4.\nREVIEW: REVISE",
        "Corrected: 2 + 2 = 4\n#### 4",
    ])
    cloud = MockCloudClient()
    strat = LocalPeerReviewStrategy(local, cloud)
    res = strat.run({"question": "What is 2 + 2?"})

    assert res["predicted_numeric"] == "4"
    assert res["cloud_calls"] == 0
    assert not res["escalated"]
    assert res["peer_saved_escalation"] is True
    assert res["peer_revisions"] == 1
    assert local.call_count == 3
    assert cloud.call_count == 0


def test_peer_review_escalates_when_revision_fails():
    # Call 1: Proposer makes mistake
    # Call 2: Critic asks for revision
    # Call 3: Proposer still makes mistake
    # Cloud resolves it!
    local = MockLocalClient([
        "2 + 2 = 5\n#### 5",
        "Arithmetic error.\nREVIEW: REVISE",
        "Still wrong: 2 + 2 = 6\n#### 6",
    ])
    cloud = MockCloudClient("Authoritative fix: 2 + 2 = 4\n#### 4", cost=0.001)
    strat = LocalPeerReviewStrategy(local, cloud)
    res = strat.run({"question": "What is 2 + 2?"})

    assert res["predicted_numeric"] == "4"
    assert res["cloud_calls"] == 1
    assert res["escalated"] is True
    assert res["peer_saved_escalation"] is False
    assert local.call_count == 3
    assert cloud.call_count == 1
