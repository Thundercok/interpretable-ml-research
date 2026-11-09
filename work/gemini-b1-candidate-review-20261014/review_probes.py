"""Offline counterexamples for the pasted candidate; does not import RAT runtime."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from external_candidate import compile_context_snapshot
from test_candidate_supplied import _base_canonical_state


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
findings = []


def record(name, expected, observed, reproduced):
    assert reproduced, (name, observed)
    findings.append({
        "name": name,
        "expected_invariant": expected,
        "observed": observed,
        "counterexample_reproduced": bool(reproduced),
    })


schema_path = ROOT / "audit/rat_context_B_assignment_20261014/snapshot.schema.json"
schema = json.loads(schema_path.read_text())
snap = compile_context_snapshot(_base_canonical_state(), strict=True)
errors = list(Draft202012Validator(schema).iter_errors(snap))
record(
    "canonical_output_schema",
    "Output conforms to the existing rat.context/1 transport schema.",
    {"schema_version": snap["schema_version"], "error_count": len(errors),
     "errors": [{"path": list(e.absolute_path), "message": e.message} for e in errors]},
    bool(errors) and snap["schema_version"] != "rat.context/1",
)

example = json.loads((ROOT / "audit/rat_context_B_assignment_20261014/after.snapshot.json").read_text())
contract = example["runtime_obligations"]["contract"]
assert contract["is_valid"] and len(contract["outcomes"]) > 0
state = _base_canonical_state()
state["contract"] = contract
state["reconciler_assessment"] = example["observed_state"]["progress"]["evidence"]
snap = compile_context_snapshot(state, strict=True)
record(
    "canonical_contract_fields_lost",
    "Preserve canonical outcomes/validation_errors/identity and read existing matched_receipts.",
    {"input_outcome_count": len(contract["outcomes"]), "exported_contract": snap["contract"],
     "progress": snap["progress"], "validation": snap["validation"]},
    snap["contract"]["is_empty"] and snap["contract"]["declarations"] == [] and not snap["progress"]["checked"],
)

state = _base_canonical_state()
state["entity_registry"]["artifact"]["art_1"] = {"revision": 2, "text": "REVISION TWO"}
state["projection_slots"] = {"old_version": {"$value_ref": {
    "namespace": "artifact", "entity_id": "art_1", "epoch": 3,
    "revision": 1, "field_path": "/text",
}}}
snap = compile_context_snapshot(state, strict=True)
slot = snap["projection_slots"]["old_version"]
record(
    "requested_revision_not_used_in_lookup",
    "A revision-1 ref must resolve revision 1 or return explicit unavailable; never revision 2.",
    {"slot": slot, "validation": snap["validation"]},
    slot["resolved"] and slot["value"] == "REVISION TWO" and slot["ref"]["revision"] == 1,
)

state = _base_canonical_state()
raw_body = {"_is_typed_slot": True, "$value_ref": {
    "namespace": "artifact", "entity_id": "art_1", "epoch": 3,
    "field_path": "/metrics/accuracy",
}}
state["entity_registry"]["artifact"]["raw_body"] = raw_body
state["projection_slots"] = {"raw": {"$value_ref": {
    "namespace": "artifact", "entity_id": "raw_body", "epoch": 3,
}}}
snap = compile_context_snapshot(state, strict=True)
record(
    "raw_body_self_declares_typed_slot",
    "Typed dereference eligibility comes from trusted projector registration, not raw payload keys.",
    {"input_body": raw_body, "resolved_slot": snap["projection_slots"]["raw"],
     "validation": snap["validation"]},
    snap["projection_slots"]["raw"]["value"] == 0.98,
)

state = _base_canonical_state()
state["quotes"] = [
    {"source": "note_alpha", "revision": "rev_1", "field": "text", "authority": "user",
     "text": "Initial", "range": [0, 7]},
    {"source": "note_alpha", "revision": "rev_1", "field": "text", "authority": "user",
     "text": "hypothesis", "range": [21, 31]},
]
snap = compile_context_snapshot(state, strict=True)
first, second = snap["quotes"]
record(
    "quote_exact_values_and_ranges_lost",
    "Distinct quoted spans retain their exact values/ranges, or remain raw when unmodeled.",
    {"input_quotes": state["quotes"], "output_quotes": snap["quotes"],
     "generated_refs": snap["quote_refs"], "validation": snap["validation"]},
    first["quote_ref"] == second["quote_ref"]
    and snap["quote_refs"][first["quote_ref"]]["text"] == "Initial draft of the hypothesis."
    and "range" not in first and "text" not in first,
)

state = _base_canonical_state()
rev = state["notes"][0]["revisions"][0]
rev.update({"confirmed": False, "source_ref": {"artifact_id": "original-source", "revision": 1},
            "source_verification": {"status": "UNKNOWN"}, "conversation_id": "conv-a"})
snap = compile_context_snapshot(state, strict=True)
lost = sorted(set(rev) - set(snap["notes"][0]["revisions"][0]))
record(
    "note_metadata_loss",
    "Retain canonical confirmation, source identity, verification and conversation metadata.",
    {"missing_input_fields": lost, "output_revision": snap["notes"][0]["revisions"][0]},
    all(key in lost for key in ("confirmed", "source_ref", "source_verification", "conversation_id")),
)

state = _base_canonical_state()
state["lifecycle_phase"] = "cancelled"
snap = compile_context_snapshot(state, strict=True)
record(
    "runtime_cancel_state_rewritten",
    "A projection retains runtime cancellation rather than replacing it with an active lifecycle.",
    snap["progress"],
    snap["progress"]["lifecycle_phase"] == "active_projection",
)

state = _base_canonical_state()
state["proposal"] = {"state": {"goal": "MODEL PROPOSAL", "completed": True}}
snap = compile_context_snapshot(state, strict=True)
record(
    "proposal_authority_and_content",
    "Model proposal retains its representation and model_proposed authority.",
    {"input": state["proposal"], "output": snap["proposal"], "validation": snap["validation"]},
    snap["proposal"]["authority"] == "system" and "state" not in snap["proposal"],
)

state = _base_canonical_state()
state["contract"].update({"is_valid": False, "validation_errors": ["invalid_binding"], "intent_coverage": "invalid"})
snap = compile_context_snapshot(state, strict=True)
record(
    "canonical_invalid_flags_ignored",
    "Canonical invalidity cannot be overridden by empty invented errors and nonempty declarations.",
    {"input_contract": state["contract"], "output_contract": snap["contract"], "progress": snap["progress"]},
    snap["contract"]["is_valid"] and snap["progress"]["status"] == "met",
)

historical_command = json.loads((ROOT / "audit/rat_core_reconciliation_fix_20261013/test_run.json").read_text())["command"]
record(
    "audit_command_not_shell_string",
    "Regression argv is executed as an argument list, not printed as Python repr and passed to eval.",
    {"command_type": type(historical_command).__name__, "script_would_print": str(historical_command),
     "execution_note": "The supplied shell script was not executed."},
    isinstance(historical_command, list),
)

output = {"scope": "Offline counterexamples for pasted external code, not production RAT tests.",
          "count": len(findings), "findings": findings}
(HERE / "probe_results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"count": len(findings), "counterexamples_reproduced": [f["name"] for f in findings]}, indent=2))
