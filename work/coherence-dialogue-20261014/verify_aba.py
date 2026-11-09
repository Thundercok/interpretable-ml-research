"""Deterministic public-API schedules; no threads, inference or dispatched tools."""
from pathlib import Path
import hashlib
import json

from rat.engine.work_notes import WorkNotebook
from rat.kernel.contracts import Artifact, ArtifactStore


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
paths = ["rat/kernel/contracts.py", "rat/engine/work_notes.py", "rat/kernel/dispatcher.py"]
start = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


notebook = WorkNotebook(conversation_id="coherence-review")
epoch = notebook.begin_request("Synthetic review", execution_id="coherence-review-execution")
notebook.select_results(["n1"], generation=epoch)


def selection_vector():
    return {"generation": notebook.generation, "cursor": notebook.event_cursor(),
            "selection_set": notebook.selection_set, "selected_ids": notebook.result_ids()}


selection_pre = selection_vector()
notebook.select_results(["n2"], generation=epoch)
selection_bundle = selection_vector()
notebook.select_results(["n1"], generation=epoch)
selection_post = selection_vector()
assert selection_pre == selection_post
assert selection_bundle != selection_pre

store = ArtifactStore()
original = Artifact(id="aba-artifact", kind="review", title="Review", revision=1, payload={"identity": "ORIGINAL"})
store.put(original)
target_before = store.get(original.id)
epoch_before = store.generation


def metadata_vector():
    return {"generation": store.generation, "members": [(a.id, a.revision) for a in store.list()]}


metadata_pre = metadata_vector()
body_before = target_before.to_dict()
assert store.delete(original.id)
store.put(Artifact(id=original.id, kind="review", title="Review", revision=1, payload={"identity": "REPLACEMENT"}))
metadata_post = metadata_vector()
body_after = store.get(original.id).to_dict()
assert metadata_pre == metadata_post
assert body_before != body_after

# Simulates a write bound only to the stale ID/revision/generation. It writes to
# an isolated in-memory store, not a real user's artifact or application state.
write = Artifact(id=target_before.id, kind="review", title="Review", revision=target_before.revision + 1,
                 payload={"identity": "WRITE_FROM_OLD_TARGET"})
accepted = store.put(write, expected_revision=target_before.revision, expected_generation=epoch_before)
assert accepted.payload == {"identity": "WRITE_FROM_OLD_TARGET"}

result = {
    "scope": "Authored deterministic schedules against current public core APIs; no B2 copier or live application integration tested.",
    "selection_aba": {
        "pre": selection_pre, "bundle": selection_bundle, "post": selection_post,
        "pre_equals_post": True, "three_way_check_would_reject": True,
        "limitation": "Selection n2 existed at an intermediate time; this case alone does not prove no common linearization point for all stores.",
    },
    "artifact_delete_recreate": {
        "metadata_pre": metadata_pre, "metadata_post": metadata_post,
        "metadata_vectors_equal": True,
        "before_body": body_before, "after_body": body_after,
        "before_digest": digest(body_before), "after_digest": digest(body_after),
        "content_digest_would_detect_change": True,
        "stale_target_write": {
            "expected_revision": target_before.revision, "expected_generation": epoch_before,
            "accepted": accepted.to_dict(),
            "limitation": "Public store guard accepts this schedule; ordinary app paths may or may not reuse deleted IDs. Runtime reachability needs separate review.",
        },
    },
    "inference_calls": 0, "operation_dispatches": 0,
    "source_sha256_start": start,
    "source_sha256_finish": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
}
assert result["source_sha256_start"] == result["source_sha256_finish"]
(HERE / "aba_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"selection_three_way_check": "rejects authored ABA schedule", "artifact_revision_reuse": "confirmed",
                  "stale_store_write_guard": "accepted old revision/generation after identity reuse",
                  "source_changed": False, "inference_calls": 0}))
