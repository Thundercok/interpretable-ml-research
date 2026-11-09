"""Check default input lifecycle using an in-memory generic registered fixture."""
from pathlib import Path
import hashlib
import json

from rat.kernel.contracts import ArtifactStore, InputRequest
from rat.kernel.dispatcher import ActionDispatcher
from rat.kernel.registry import CapabilityRegistry, OperationDefinition


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
source_paths = ["rat/kernel/contracts.py", "rat/kernel/dispatcher.py", "rat/kernel/registry.py"]
start = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths}


def handler(args, **context):
    missing = [name for name in ("first", "second") if name not in args]
    if missing:
        return InputRequest("identity_review_fixture", supplied_inputs=dict(args),
                            missing_fields=[{"name": name, "type": "string"} for name in missing])
    return {"value": args["first"] + args["second"]}


registry = CapabilityRegistry()
registry.register_operation(OperationDefinition(
    "identity_review_fixture", "Synthetic identity review", {
        "type": "object", "properties": {"first": {"type": "string"}, "second": {"type": "string"}},
    }, handler, artifact_kind="identity_review_fixture",
))
store = ArtifactStore()
dispatcher = ActionDispatcher(registry, store)
first = dispatcher.execute_operation("identity_review_fixture", {"first": "a"})
assert first.status == "needs_input" and first.artifact.revision == 1
request_id = first.input_request.id
continued = dispatcher.resume_input(request_id, {})
assert continued.status == "needs_input"
assert continued.input_request.id == request_id and continued.artifact.revision == 2
complete = dispatcher.resume_input(request_id, {"second": "b"})
assert complete.status == "success" and complete.result == {"value": "ab"}
assert store.get(request_id) is None and dispatcher.state.pending_input_request is None
closed_resume = dispatcher.resume_input(request_id, {"second": "c"})
assert closed_resume.status == "error"
fresh = dispatcher.execute_operation("identity_review_fixture", {"first": "x"})
assert fresh.status == "needs_input" and fresh.artifact.revision == 1
assert fresh.input_request.id != request_id

end = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths}
assert start == end
result = {
    "scope": "Generic in-memory handler/dispatcher fixture; not personal-index, UI, model or B1/B2 integration evidence.",
    "observations": {
        "initial": {"request_id": request_id, "revision": first.artifact.revision},
        "continued_wait": {"request_id": continued.input_request.id, "revision": continued.artifact.revision},
        "complete_status": complete.status,
        "closed_resume_status": closed_resume.status,
        "fresh": {"request_id": fresh.input_request.id, "revision": fresh.artifact.revision},
    },
    "inference_calls": 0,
    "fixture_handler_invocations": 4,
    "source_sha256_start": start, "source_sha256_finish": end,
}
(HERE / "input_lifecycle_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"initial_revision": 1, "continued_revision": 2, "request_deleted_on_success": True,
                  "old_resume_rejected": True, "fresh_request_id": True, "inference_calls": 0}))
