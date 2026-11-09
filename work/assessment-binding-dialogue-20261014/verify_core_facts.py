"""Small headless checks supporting design review; no operations are dispatched."""
from pathlib import Path
import hashlib
import json

from rat.engine.completion import ExecutionJournal, OutcomeSpec, TurnContract, reconcile_turn
from rat.kernel.contracts import Artifact, ArtifactStore
from rat.engine.work_notes import WorkNotebook


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent
source_paths = [
    "rat/engine/completion.py", "rat/engine/work_notes.py", "rat/kernel/contracts.py",
    "rat/engine/assistant_runtime.py", "audit/rat_context_B_assignment_20261014/decisions.md",
]
start_hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths}
scope = dict(contract_id="binding-review-contract", conversation_id="binding-review-conversation",
             turn_id="binding-review-turn", execution_id="binding-review-execution", generation=3)


def contract(value):
    return TurnContract(**scope, outcomes=[OutcomeSpec(
        outcome_id="effect-1", kind="registered_effect", effect_type="review_only_effect",
        expected_args={"value": value},
    )])


journal = ExecutionJournal(conversation_id=scope["conversation_id"], turn_id=scope["turn_id"],
                           execution_id=scope["execution_id"], generation=3)
# Authored synthetic receipt only; this does not dispatch or execute an operation.
journal.record_operation("review_only_effect", {"value": 1}, {"ok": True})
first, second = contract(1), contract(2)
report_first = reconcile_turn(first, journal, lifecycle="in_progress", final_answer="").to_dict()
report_second = reconcile_turn(second, journal, lifecycle="in_progress", final_answer="").to_dict()
assert first.is_valid and second.is_valid
assert first.contract_id == second.contract_id and first.generation == second.generation
assert [o.outcome_id for o in first.outcomes] == [o.outcome_id for o in second.outcomes]
assert report_first["unmet_outcomes"] == []
assert report_second["unmet_outcomes"][0]["reason"] == "input_mismatch"
assert report_first["semantic_limitation"] and report_second["semantic_limitation"]

store = ArtifactStore()
store.put(Artifact(id="binding-review-artifact", kind="review", title="Review", payload={"value": 1}, revision=1))
epoch_before_update = store.generation
store.put(Artifact(id="binding-review-artifact", kind="review", title="Review", payload={"value": 2}, revision=2))
assert store.generation == epoch_before_update
assert store.get("binding-review-artifact").revision == 2
store.delete("binding-review-artifact")
assert store.generation == epoch_before_update

notebook = WorkNotebook(conversation_id="binding-review-conversation")
generation = notebook.begin_request("Synthetic design review", execution_id="binding-review-execution")
cursor_before = notebook.event_cursor()
notebook.select_results(["result-a"], generation=generation)
assert notebook.event_cursor() == cursor_before
assert notebook.generation == generation
assert notebook.selection_set and notebook.result_ids() == ["result-a"]

result = {
    "scope": "Synthetic headless design checks on the existing core, not production B1 acceptance or model-quality measurement.",
    "inference_calls": 0,
    "operation_dispatches": 0,
    "facts": {
        "same_binding_different_expected_args": {
            "first_contract": first.to_dict(), "second_contract": second.to_dict(),
            "first_assessment": report_first, "second_assessment": report_second,
            "journal": journal.to_dict(),
        },
        "semantic_limitation_is_nonempty_on_complete_valid_assessment": True,
        "artifact_update_and_delete_do_not_increment_generation": True,
        "selection_change_does_not_increment_note_cursor_or_generation": True,
    },
    "source_sha256_start": start_hashes,
    "source_sha256_finish": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths},
}
result["source_changed_during_check"] = [p for p in source_paths if start_hashes[p] != result["source_sha256_finish"][p]]
assert result["source_changed_during_check"] == []
(OUTPUT / "core_facts.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"checks": 4, "passed": True, "source_changed": [], "inference_calls": 0, "operation_dispatches": 0}))
