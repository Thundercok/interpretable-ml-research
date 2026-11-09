# tests/test_context_snapshot_b1.py
from __future__ import annotations

import copy
import pytest

from external_candidate import (
    SnapshotCompilationError,
    compile_context_snapshot,
)


def _base_canonical_state() -> dict:
    return {
        "coherence": {
            "artifact_epoch": 3,
            "notebook_epoch": 5,
            "selection_set": True,
            "selected_ids": ["art_1"],
        },
        "proposal": {
            "proposal_id": "prop_101",
            "authority": "system",
            "expected_args": {"query": "test", "raw_wrapper": {"$value_ref": "do_not_touch"}},
            "payload": {"action": "summarize"},
        },
        "contract": {
            "declarations": [{"id": "decl_1", "rule": "must_cite_source"}],
            "errors": [],
            "frozen": True,
        },
        "reconciler_assessment": {
            "checked": True,
            "status": "met",
            "matched_receipt_ids": ["rcpt_1"],
        },
        "receipts": [
            {"receipt_id": "rcpt_1", "tool": "verifier", "verified": True},
        ],
        "proofs": [
            {"proof_id": "prf_1", "digest": "abc12345"},
        ],
        "notes": [
            {
                "note_id": "note_alpha",
                "revisions": [
                    {
                        "revision_id": "rev_1",
                        "text": "Initial draft of the hypothesis.",
                        "status": "superseded",
                        "source": "note_alpha",
                        "authority": "user",
                        "owner": "researcher_a",
                        "epoch": 4,
                        "replaces": None,
                        "replaced_by": "rev_2",
                    },
                    {
                        "revision_id": "rev_2",
                        "text": "Refined hypothesis with statistical bounds.",
                        "status": "active",
                        "source": "note_alpha",
                        "authority": "user",
                        "owner": "researcher_a",
                        "epoch": 5,
                        "replaces": "rev_1",
                        "replaced_by": None,
                    },
                ],
            }
        ],
        "quotes": [
            {
                "source": "note_alpha",
                "revision": "rev_1",
                "field": "text",
                "authority": "derived",
            },
            {
                "source": "note_alpha",
                "revision": "rev_1",
                "field": "text",
                "authority": "tool",
            },
        ],
        "operations": [
            {
                "op_id": "op_art",
                "op_type": "extract_table",
                "authority": "tool",
                "expected_args": {"page": 2},
                "input_values": {"mock_ref": {"$value_ref": "keep_raw_in_input"}},
                "result": {
                    "result_kind": "artifact",
                    "artifact_id": "art_1",
                    "epoch": 3,
                    "payload": {"rows": 12},
                },
            },
            {
                "op_id": "op_scalar",
                "op_type": "count_tokens",
                "authority": "tool",
                "expected_args": {},
                "input_values": {"text": "hello"},
                "result": {
                    "result_kind": "scalar",
                    "payload": 42,
                },
            },
            {
                "op_id": "op_unknown",
                "op_type": "custom_plugin",
                "authority": "user",
                "expected_args": {},
                "input_values": {},
                "result": {"arbitrary_unmodeled_key": [1, 2, 3]},
            },
        ],
        "entity_registry": {
            "artifact": {
                "art_1": {"title": "Table 1", "metrics": {"accuracy": 0.98}},
            }
        },
        "projection_slots": {
            "primary_metric": {
                "$value_ref": {
                    "namespace": "artifact",
                    "entity_id": "art_1",
                    "epoch": 3,
                    "field_path": "/metrics/accuracy",
                }
            }
        },
        "user_payload": {
            "nested": {"$value_ref": {"namespace": "artifact", "entity_id": "art_1"}}
        },
        "lifecycle_phase": "active",
    }


def test_lossless_reconstruction_and_input_immutability():
    state = _base_canonical_state()
    frozen_before = copy.deepcopy(state)

    snap = compile_context_snapshot(state, strict=True)

    # Compiler must not mutate input
    assert state == frozen_before
    assert snap["validation"]["is_clean"] is True
    assert snap["contract"]["frozen"] is True
    assert snap["contract"]["declarations"] == [{"id": "decl_1", "rule": "must_cite_source"}]
    assert snap["projection_slots"]["primary_metric"]["value"] == 0.98


def test_distinct_authority_preserved():
    state = _base_canonical_state()
    snap = compile_context_snapshot(state, strict=True)

    assert snap["proposal"]["authority"] == "system"
    assert snap["notes"][0]["revisions"][0]["authority"] == "user"
    assert snap["operations"][0]["authority"] == "tool"
    assert snap["operations"][2]["authority"] == "user"
    assert snap["quotes"][0]["authority"] == "derived"
    assert snap["quotes"][1]["authority"] == "tool"


def test_operation_artifact_no_artifact_and_unknown_fallback():
    state = _base_canonical_state()
    snap = compile_context_snapshot(state, strict=True)
    ops = {op["op_id"]: op for op in snap["operations"]}

    assert ops["op_art"]["result"]["kind"] == "artifact"
    assert ops["op_art"]["result"]["has_artifact"] is True
    assert ops["op_art"]["result"]["artifact_ref"]["entity_id"] == "art_1"

    assert ops["op_scalar"]["result"]["kind"] == "no_artifact"
    assert ops["op_scalar"]["result"]["has_artifact"] is False
    assert ops["op_scalar"]["result"]["value"] == 42

    assert ops["op_unknown"]["result"]["kind"] == "raw_fallback"
    assert ops["op_unknown"]["result"]["raw_result"] == {"arbitrary_unmodeled_key": [1, 2, 3]}


@pytest.mark.parametrize(
    "contract,assessment,expected_status",
    [
        ({"declarations": [], "errors": [], "frozen": False}, {"checked": True, "status": "met", "matched_receipt_ids": ["rcpt_1"]}, "empty"),
        ({"declarations": [{"id": "d1"}], "errors": ["syntax_err"], "frozen": False}, {"checked": True, "status": "met", "matched_receipt_ids": ["rcpt_1"]}, "invalid"),
        ({"declarations": [{"id": "d1"}], "errors": [], "frozen": True}, {"checked": False, "status": "met", "matched_receipt_ids": ["rcpt_1"]}, "unchecked"),
        ({"declarations": [{"id": "d1"}], "errors": [], "frozen": True}, {"checked": True, "status": "met", "matched_receipt_ids": []}, "unmet"),
    ],
)
def test_empty_invalid_or_unchecked_contract_never_becomes_met(contract, assessment, expected_status):
    state = _base_canonical_state()
    state["contract"] = contract
    state["reconciler_assessment"] = assessment
    snap = compile_context_snapshot(state)

    assert snap["progress"]["status"] == expected_status
    assert snap["progress"]["status"] != "met"
    assert snap["progress"]["response_state"] == "pending"


def test_stale_generation_epoch_detection():
    state = _base_canonical_state()
    # Slot points to epoch 2 while snapshot artifact_epoch is 3
    state["projection_slots"]["primary_metric"]["$value_ref"]["epoch"] = 2
    snap = compile_context_snapshot(state)

    assert snap["validation"]["is_clean"] is False
    codes = {i["code"] for i in snap["validation"]["issues"]}
    assert "stale_generation" in codes
    assert snap["projection_slots"]["primary_metric"]["resolved"] is False

    with pytest.raises(SnapshotCompilationError):
        compile_context_snapshot(state, strict=True)


def test_missing_and_cyclic_value_refs():
    state = _base_canonical_state()
    state["entity_registry"]["slot"] = {
        "slot_a": {"_is_typed_slot": True, "$value_ref": {"namespace": "slot", "entity_id": "slot_b"}},
        "slot_b": {"_is_typed_slot": True, "$value_ref": {"namespace": "slot", "entity_id": "slot_a"}},
    }
    state["projection_slots"]["cyclic_slot"] = {
        "$value_ref": {"namespace": "slot", "entity_id": "slot_a"}
    }
    state["projection_slots"]["missing_slot"] = {
        "$value_ref": {"namespace": "artifact", "entity_id": "non_existent", "epoch": 3}
    }

    snap = compile_context_snapshot(state)
    codes = {i["code"] for i in snap["validation"]["issues"]}
    assert "cyclic_value_ref" in codes
    assert "missing_value_ref_target" in codes
    assert snap["projection_slots"]["cyclic_slot"]["mode"] == "cyclic_ref"
    assert snap["projection_slots"]["missing_slot"]["mode"] == "missing_ref"


def test_raw_fake_wrapper_not_dereferenced():
    state = _base_canonical_state()
    snap = compile_context_snapshot(state, strict=True)

    # User JSON, expected_args, and operation input_values with "$value_ref" must remain raw
    assert snap["user_payload"]["nested"] == {
        "$value_ref": {"namespace": "artifact", "entity_id": "art_1"}
    }
    assert snap["proposal"]["expected_args"]["raw_wrapper"] == {"$value_ref": "do_not_touch"}
    assert snap["operations"][0]["input_values"]["mock_ref"] == {"$value_ref": "keep_raw_in_input"}


def test_note_revisions_inline_and_quote_dedup_and_id_only_rejection():
    state = _base_canonical_state()
    snap = compile_context_snapshot(state, strict=True)

    revs = snap["notes"][0]["revisions"]
    assert len(revs) == 2
    assert revs[0]["text"] == "Initial draft of the hypothesis."
    assert revs[0]["replacement_links"] == {"replaces": None, "replaced_by": "rev_2"}
    assert revs[1]["replacement_links"] == {"replaces": "rev_1", "replaced_by": None}

    # Both quotes target (note_alpha, rev_1, text) -> must share deterministic quote_ref
    q1, q2 = snap["quotes"]
    assert q1["resolved"] is True and q2["resolved"] is True
    assert q1["quote_ref"] == q2["quote_ref"]
    assert q1["quote_ref"] in snap["quote_refs"]

    # ID-only note without inline revisions must trigger validation issue
    bad_state = _base_canonical_state()
    bad_state["notes"].append({"note_id": "dangling_old_note"})
    bad_snap = compile_context_snapshot(bad_state)
    assert any(i["code"] == "id_only_or_missing_revisions" for i in bad_snap["validation"]["issues"])


def test_selection_set_false_vs_true_with_empty_list():
    state_unset = _base_canonical_state()
    state_unset["coherence"] = {
        "artifact_epoch": 1,
        "notebook_epoch": 1,
        "selection_set": False,
        "selected_ids": [],
    }

    state_empty_selection = _base_canonical_state()
    state_empty_selection["coherence"] = {
        "artifact_epoch": 1,
        "notebook_epoch": 1,
        "selection_set": True,
        "selected_ids": [],
    }

    snap_unset = compile_context_snapshot(state_unset, strict=True)
    snap_empty = compile_context_snapshot(state_empty_selection, strict=True)

    assert snap_unset["coherence"]["selection_set"] is False
    assert snap_empty["coherence"]["selection_set"] is True
    assert snap_unset["coherence"] != snap_empty["coherence"]

