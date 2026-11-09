from benchmarks.selective_delegation.datasets.gsm8k import load_gsm8k
from benchmarks.selective_delegation.strategies.local_only import extract_numeric_answer, LocalOnlyStrategy


def test_extracts_gsm8k_style_final_answer():
    assert extract_numeric_answer("Work...\n#### 1,234") == "1234"


def test_fallback_uses_last_number():
    assert extract_numeric_answer("There are 3 groups of 4, so 12.") == "12"


def test_missing_answer_returns_none():
    assert extract_numeric_answer("I cannot solve this.") is None


def test_local_only_never_calls_cloud_and_records_metadata():
    class FakeClient:
        def chat_with_meta(self, messages, tools, **kwargs):
            assert tools == []
            return {"message": {"content": "#### 42"}, "prompt_tokens": 10,
                    "completion_tokens": 3, "token_usage_known": True, "duration_ms": 12}
    result = LocalOnlyStrategy(FakeClient()).run({"question": "What is 6 times 7?"})
    assert result["predicted_numeric"] == "42"
    assert result["cloud_calls"] == 0
    assert result["verification_status"] == "NOT_RUN"


def test_gsm8k_loader_normalizes_answer_and_is_deterministic(tmp_path):
    import json
    path = tmp_path / "test.jsonl"
    rows = [
        {"question": f"Q{i}", "answer": f"reasoning\n#### {i * 10:,}"}
        for i in range(30)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    first = load_gsm8k(path, limit=20, seed=42)
    second = load_gsm8k(path, limit=20, seed=42)
    assert first == second
    assert len(first) == 20
    assert all(row["ground_truth"] == str(int(row["ground_truth_numeric"])) for row in first)
