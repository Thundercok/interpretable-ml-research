# rat/engine/context_snapshot.py
"""Headless Context Projection Compiler (B1).

Pure compiler transforming canonical input copies into validated context snapshots
and projection/render payloads without side effects, UI dependencies, personal index
reads, or model invocations.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

SNAPSHOT_SCHEMA_VERSION = "1.0.0-b1"

VALID_NAMESPACES = frozenset({
    "artifact",
    "notebook",
    "note_revision",
    "quote",
    "operation",
    "receipt",
    "proof",
    "contract",
    "slot",
})

VALID_AUTHORITIES = frozenset({
    "user",
    "system",
    "tool",
    "reconciler",
    "derived",
})

TERMINAL_LIFECYCLE_STATES = frozenset({"completed", "failed", "aborted", "cancelled"})


class SnapshotCompilationError(ValueError):
    """Raised when structural invariants fail and strict validation is requested."""


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    pointer: str
    message: str
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "pointer": self.pointer,
            "message": self.message,
            "detail": copy.deepcopy(dict(self.detail)),
        }


@dataclass(frozen=True)
class EntityRef:
    namespace: str
    entity_id: str
    epoch: int | None = None
    revision: str | int | None = None
    field_path: str | None = None

    def validate(self, pointer: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if self.namespace not in VALID_NAMESPACES:
            issues.append(
                ValidationIssue(
                    code="invalid_namespace",
                    pointer=pointer,
                    message=f"Unknown entity namespace: {self.namespace!r}",
                    detail={"namespace": self.namespace},
                )
            )
        if not isinstance(self.entity_id, str) or not self.entity_id.strip():
            issues.append(
                ValidationIssue(
                    code="invalid_entity_id",
                    pointer=pointer,
                    message="Entity ID must be a non-empty string.",
                )
            )
        if self.field_path is not None and not self.field_path.startswith("/"):
            issues.append(
                ValidationIssue(
                    code="invalid_json_pointer",
                    pointer=pointer,
                    message=f"Field path must be a JSON pointer starting with '/': {self.field_path!r}",
                    detail={"field_path": self.field_path},
                )
            )
        return issues

    def canonical_uri(self) -> str:
        base = f"rat://{self.namespace}/{self.entity_id}"
        qualifiers: list[str] = []
        if self.revision is not None:
            qualifiers.append(f"rev={self.revision}")
        if self.epoch is not None:
            qualifiers.append(f"epoch={self.epoch}")
        if qualifiers:
            base = f"{base}?{'&'.join(qualifiers)}"
        if self.field_path:
            base = f"{base}#{self.field_path}"
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "entity_id": self.entity_id,
            "epoch": self.epoch,
            "revision": self.revision,
            "field_path": self.field_path,
            "uri": self.canonical_uri(),
        }


@dataclass(frozen=True)
class CoherenceMetadata:
    artifact_epoch: int
    notebook_epoch: int
    selection_set: bool
    selected_ids: tuple[str, ...] = ()

    def validate(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not isinstance(self.artifact_epoch, int) or isinstance(self.artifact_epoch, bool) or self.artifact_epoch < 0:
            issues.append(
                ValidationIssue(
                    code="invalid_artifact_epoch",
                    pointer="/coherence/artifact_epoch",
                    message="artifact_epoch must be a non-negative integer.",
                )
            )
        if not isinstance(self.notebook_epoch, int) or isinstance(self.notebook_epoch, bool) or self.notebook_epoch < 0:
            issues.append(
                ValidationIssue(
                    code="invalid_notebook_epoch",
                    pointer="/coherence/notebook_epoch",
                    message="notebook_epoch must be a non-negative integer.",
                )
            )
        if not isinstance(self.selection_set, bool):
            issues.append(
                ValidationIssue(
                    code="invalid_selection_flag",
                    pointer="/coherence/selection_set",
                    message="selection_set must be an explicit boolean.",
                )
            )
        if not self.selection_set and len(self.selected_ids) != 0:
            issues.append(
                ValidationIssue(
                    code="inconsistent_selection_state",
                    pointer="/coherence/selected_ids",
                    message="selected_ids must be empty when selection_set is False.",
                )
            )
        return issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_epoch": self.artifact_epoch,
            "notebook_epoch": self.notebook_epoch,
            "selection_set": self.selection_set,
            "selected_ids": list(self.selected_ids) if self.selection_set else [],
        }


def _generate_quote_ref_id(source: str, revision: str | int, field_name: str, text: str) -> str:
    payload = json.dumps(
        {"source": source, "revision": str(revision), "field": field_name, "text": text},
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"qref_{digest}"


def _resolve_typed_slot_value(
    slot_name: str,
    raw_slot_spec: Any,
    registry: Mapping[str, Any],
    coherence: CoherenceMetadata,
    issues: list[ValidationIssue],
    visited: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Decode $value_ref strictly inside declared typed projection slots.

    Prevents cyclic references, missing target crashes, and stale epoch adoption.
    """
    pointer = f"/projection_slots/{slot_name}"
    if not isinstance(raw_slot_spec, Mapping) or "$value_ref" not in raw_slot_spec:
        return {
            "slot": slot_name,
            "mode": "literal",
            "resolved": True,
            "value": copy.deepcopy(raw_slot_spec),
            "ref": None,
        }

    ref_payload = raw_slot_spec["$value_ref"]
    if not isinstance(ref_payload, Mapping):
        issues.append(
            ValidationIssue(
                code="malformed_value_ref",
                pointer=f"{pointer}/$value_ref",
                message="$value_ref in a typed slot must be a mapping.",
            )
        )
        return {
            "slot": slot_name,
            "mode": "unresolved_ref",
            "resolved": False,
            "value": None,
            "raw_fallback": copy.deepcopy(raw_slot_spec),
        }

    entity_ref = EntityRef(
        namespace=str(ref_payload.get("namespace", "")),
        entity_id=str(ref_payload.get("entity_id", "")),
        epoch=ref_payload.get("epoch"),
        revision=ref_payload.get("revision"),
        field_path=ref_payload.get("field_path"),
    )
    ref_issues = entity_ref.validate(f"{pointer}/$value_ref")
    issues.extend(ref_issues)
    uri = entity_ref.canonical_uri()

    if uri in visited:
        issues.append(
            ValidationIssue(
                code="cyclic_value_ref",
                pointer=f"{pointer}/$value_ref",
                message=f"Cyclic $value_ref detected at {uri}",
                detail={"cycle_uri": uri, "chain": list(visited)},
            )
        )
        return {
            "slot": slot_name,
            "mode": "cyclic_ref",
            "resolved": False,
            "ref": entity_ref.to_dict(),
            "value": None,
        }

    # Check epoch coherence before dereferencing
    if entity_ref.namespace == "artifact" and entity_ref.epoch is not None:
        if entity_ref.epoch != coherence.artifact_epoch:
            issues.append(
                ValidationIssue(
                    code="stale_generation",
                    pointer=f"{pointer}/$value_ref/epoch",
                    message=(
                        f"Artifact ref epoch ({entity_ref.epoch}) mismatches snapshot "
                        f"artifact_epoch ({coherence.artifact_epoch})."
                    ),
                    detail={
                        "ref_epoch": entity_ref.epoch,
                        "snapshot_epoch": coherence.artifact_epoch,
                    },
                )
            )
            return {
                "slot": slot_name,
                "mode": "stale_ref",
                "resolved": False,
                "ref": entity_ref.to_dict(),
                "value": None,
            }

    if entity_ref.namespace in ("notebook", "note_revision") and entity_ref.epoch is not None:
        if entity_ref.epoch != coherence.notebook_epoch:
            issues.append(
                ValidationIssue(
                    code="stale_generation",
                    pointer=f"{pointer}/$value_ref/epoch",
                    message=(
                        f"Notebook ref epoch ({entity_ref.epoch}) mismatches snapshot "
                        f"notebook_epoch ({coherence.notebook_epoch})."
                    ),
                    detail={
                        "ref_epoch": entity_ref.epoch,
                        "snapshot_epoch": coherence.notebook_epoch,
                    },
                )
            )
            return {
                "slot": slot_name,
                "mode": "stale_ref",
                "resolved": False,
                "ref": entity_ref.to_dict(),
                "value": None,
            }

    ns_bucket = registry.get(entity_ref.namespace, {})
    if not isinstance(ns_bucket, Mapping) or entity_ref.entity_id not in ns_bucket:
        issues.append(
            ValidationIssue(
                code="missing_value_ref_target",
                pointer=f"{pointer}/$value_ref",
                message=f"Target entity {uri} not found in canonical registry.",
                detail={"uri": uri},
            )
        )
        return {
            "slot": slot_name,
            "mode": "missing_ref",
            "resolved": False,
            "ref": entity_ref.to_dict(),
            "value": None,
        }

    target_obj = ns_bucket[entity_ref.entity_id]

    # Follow chaining if target is itself a typed slot wrapper
    if isinstance(target_obj, Mapping) and "$value_ref" in target_obj and target_obj.get("_is_typed_slot") is True:
        chained = _resolve_typed_slot_value(
            slot_name=slot_name,
            raw_slot_spec=target_obj,
            registry=registry,
            coherence=coherence,
            issues=issues,
            visited=visited | {uri},
        )
        return {
            "slot": slot_name,
            "mode": chained["mode"],
            "resolved": chained["resolved"],
            "ref": entity_ref.to_dict(),
            "value": chained["value"],
        }

    resolved_val = copy.deepcopy(target_obj)
    if entity_ref.field_path:
        parts = [p for p in entity_ref.field_path.split("/") if p]
        curr: Any = resolved_val
        for part in parts:
            if isinstance(curr, Mapping) and part in curr:
                curr = curr[part]
            else:
                issues.append(
                    ValidationIssue(
                        code="missing_field_pointer",
                        pointer=f"{pointer}/$value_ref/field_path",
                        message=f"Field path {entity_ref.field_path!r} not found on {uri}.",
                    )
                )
                return {
                    "slot": slot_name,
                    "mode": "missing_field",
                    "resolved": False,
                    "ref": entity_ref.to_dict(),
                    "value": None,
                }
        resolved_val = copy.deepcopy(curr)

    return {
        "slot": slot_name,
        "mode": "ref",
        "resolved": True,
        "ref": entity_ref.to_dict(),
        "value": resolved_val,
    }


def _compile_contract_and_progress(
    raw_contract: Mapping[str, Any] | None,
    reconciler_assessment: Mapping[str, Any] | None,
    actual_receipts: Sequence[Mapping[str, Any]],
    actual_proofs: Sequence[Mapping[str, Any]],
    lifecycle_phase: str,
    issues: list[ValidationIssue],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compile contract export and progress strictly from existing reconciler assessment.

    - Never fabricates outcome->receipt mappings.
    - Empty, invalid, or unchecked contracts never become 'met'.
    - Response state stays 'pending' before final lifecycle phase.
    - Does not use terminal summary as runtime lifecycle.
    """
    if raw_contract is None:
        contract_export = {
            "declarations": [],
            "errors": ["missing_contract"],
            "frozen": False,
            "is_valid": False,
            "is_empty": True,
        }
    else:
        declarations = copy.deepcopy(list(raw_contract.get("declarations", [])))
        errors = copy.deepcopy(list(raw_contract.get("errors", [])))
        frozen = bool(raw_contract.get("frozen", False))
        is_empty = len(declarations) == 0
        is_valid = len(errors) == 0 and not is_empty
        contract_export = {
            "declarations": declarations,
            "errors": errors,
            "frozen": frozen,
            "is_valid": is_valid,
            "is_empty": is_empty,
        }

    receipts_by_id: dict[str, dict[str, Any]] = {}
    for idx, r in enumerate(actual_receipts):
        r_copy = copy.deepcopy(dict(r))
        r_id = str(r_copy.get("receipt_id", f"receipt_{idx}"))
        receipts_by_id[r_id] = r_copy

    proofs_by_id: dict[str, dict[str, Any]] = {}
    for idx, p in enumerate(actual_proofs):
        p_copy = copy.deepcopy(dict(p))
        p_id = str(p_copy.get("proof_id", f"proof_{idx}"))
        proofs_by_id[p_id] = p_copy

    # Inspect reconciler_assessment without inventing new matches
    checked = bool(reconciler_assessment.get("checked", False)) if reconciler_assessment else False
    raw_matched_ids = (
        list(reconciler_assessment.get("matched_receipt_ids", []))
        if reconciler_assessment
        else []
    )

    matched_evidence: list[dict[str, Any]] = []
    for r_id in raw_matched_ids:
        if r_id in receipts_by_id:
            matched_evidence.append(receipts_by_id[r_id])
        else:
            issues.append(
                ValidationIssue(
                    code="unresolved_receipt_evidence",
                    pointer="/progress/matched_receipt_evidence",
                    message=f"Reconciler assessment referenced unknown receipt_id: {r_id!r}",
                    detail={"receipt_id": r_id},
                )
            )

    # Determine status strictly
    if not contract_export["is_valid"]:
        status = "invalid" if contract_export["errors"] else "empty"
    elif not checked:
        status = "unchecked"
    else:
        reconciler_status = str(reconciler_assessment.get("status", "unmet"))
        # Guard: even if reconciler claimed 'met', verify non-empty matched evidence exists
        if reconciler_status == "met" and len(matched_evidence) > 0:
            status = "met"
        else:
            status = "unmet"

    is_final_phase = lifecycle_phase in ("final", "completed")
    response_state = "finalized" if (is_final_phase and status == "met") else "pending"

    progress = {
        "status": status,
        "checked": checked,
        "response_state": response_state,
        "lifecycle_phase": lifecycle_phase if lifecycle_phase not in TERMINAL_LIFECYCLE_STATES else "active_projection",
        "matched_receipt_evidence": matched_evidence,
        "receipt_catalog": list(receipts_by_id.values()),
        "proof_catalog": list(proofs_by_id.values()),
    }
    return contract_export, progress


def _compile_notes_and_quotes(
    raw_notes: Sequence[Mapping[str, Any]],
    raw_quotes: Sequence[Mapping[str, Any]],
    coherence: CoherenceMetadata,
    issues: list[ValidationIssue],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Compile note revisions with inline text, authority, replacement links, and quote deduplication."""
    compiled_notes: list[dict[str, Any]] = []
    revision_index: dict[tuple[str, str], dict[str, Any]] = {}

    for idx, note in enumerate(raw_notes):
        pointer = f"/notes/{idx}"
        note_id = str(note.get("note_id", ""))
        revisions_raw = note.get("revisions")

        if not revisions_raw or not isinstance(revisions_raw, Sequence):
            issues.append(
                ValidationIssue(
                    code="id_only_or_missing_revisions",
                    pointer=pointer,
                    message=f"Note {note_id!r} is missing inline revisions; ID-only historical notes are forbidden.",
                    detail={"note_id": note_id},
                )
            )
            continue

        compiled_revs: list[dict[str, Any]] = []
        for r_idx, rev in enumerate(revisions_raw):
            r_ptr = f"{pointer}/revisions/{r_idx}"
            rev_id = str(rev.get("revision_id", ""))
            text = rev.get("text")
            authority = str(rev.get("authority", ""))
            status = str(rev.get("status", "active"))
            source = str(rev.get("source", note_id))
            owner = str(rev.get("owner", "unknown"))
            rev_epoch = rev.get("epoch", coherence.notebook_epoch)

            if not isinstance(text, str):
                issues.append(
                    ValidationIssue(
                        code="missing_inline_note_text",
                        pointer=f"{r_ptr}/text",
                        message=f"Note {note_id!r} revision {rev_id!r} must include full inline text.",
                    )
                )
            if authority not in VALID_AUTHORITIES:
                issues.append(
                    ValidationIssue(
                        code="invalid_note_authority",
                        pointer=f"{r_ptr}/authority",
                        message=f"Invalid or missing authority {authority!r} on note {note_id!r}.",
                    )
                )
            if isinstance(rev_epoch, int) and rev_epoch > coherence.notebook_epoch:
                issues.append(
                    ValidationIssue(
                        code="stale_generation",
                        pointer=f"{r_ptr}/epoch",
                        message=(
                            f"Note revision epoch ({rev_epoch}) exceeds snapshot "
                            f"notebook_epoch ({coherence.notebook_epoch})."
                        ),
                    )
                )

            replacement_links = {
                "replaces": copy.deepcopy(rev.get("replaces")),
                "replaced_by": copy.deepcopy(rev.get("replaced_by")),
            }

            rev_entry = {
                "note_id": note_id,
                "revision_id": rev_id,
                "text": text if isinstance(text, str) else "",
                "status": status,
                "source": source,
                "authority": authority,
                "owner": owner,
                "epoch": rev_epoch,
                "replacement_links": replacement_links,
            }
            compiled_revs.append(rev_entry)
            revision_index[(source, rev_id)] = rev_entry
            revision_index[(note_id, rev_id)] = rev_entry

        compiled_notes.append({
            "note_id": note_id,
            "revisions": compiled_revs,
        })

    # Compile quotes and generate deterministic refs for matching (source, revision, field)
    generated_quote_refs: dict[str, dict[str, Any]] = {}
    compiled_quotes: list[dict[str, Any]] = []

    for q_idx, quote in enumerate(raw_quotes):
        q_ptr = f"/quotes/{q_idx}"
        source = str(quote.get("source", ""))
        revision = str(quote.get("revision", ""))
        field_name = str(quote.get("field", "text"))
        authority = str(quote.get("authority", "derived"))

        if authority not in VALID_AUTHORITIES:
            issues.append(
                ValidationIssue(
                    code="invalid_quote_authority",
                    pointer=f"{q_ptr}/authority",
                    message=f"Unknown quote authority {authority!r}.",
                )
            )

        target_rev = revision_index.get((source, revision))
        if target_rev is None:
            issues.append(
                ValidationIssue(
                    code="unresolved_quote_source",
                    pointer=q_ptr,
                    message=f"Quote references unknown (source={source!r}, revision={revision!r}).",
                )
            )
            compiled_quotes.append({
                "source": source,
                "revision": revision,
                "field": field_name,
                "authority": authority,
                "resolved": False,
                "quote_ref": None,
                "raw_quote": copy.deepcopy(dict(quote)),
            })
            continue

        field_val = str(target_rev.get(field_name, ""))
        qref_id = _generate_quote_ref_id(source, revision, field_name, field_val)
        if qref_id not in generated_quote_refs:
            generated_quote_refs[qref_id] = {
                "quote_ref": qref_id,
                "source": source,
                "revision": revision,
                "field": field_name,
                "text": field_val,
                "source_authority": target_rev["authority"],
            }

        compiled_quotes.append({
            "source": source,
            "revision": revision,
            "field": field_name,
            "authority": authority,
            "resolved": True,
            "quote_ref": qref_id,
        })

    return compiled_notes, generated_quote_refs, compiled_quotes


def _compile_operations(
    raw_operations: Sequence[Mapping[str, Any]],
    coherence: CoherenceMetadata,
    issues: list[ValidationIssue],
) -> list[dict[str, Any]]:
    """Compile operations preserving native expected_args and input_values verbatim.

    Supports artifact-bearing results, no-artifact results, and raw unknown result fallback.
    """
    compiled_ops: list[dict[str, Any]] = []
    for idx, op in enumerate(raw_operations):
        ptr = f"/operations/{idx}"
        op_id = str(op.get("op_id", f"op_{idx}"))
        op_type = str(op.get("op_type", "unknown"))
        authority = str(op.get("authority", "tool"))

        if authority not in VALID_AUTHORITIES:
            issues.append(
                ValidationIssue(
                    code="invalid_operation_authority",
                    pointer=f"{ptr}/authority",
                    message=f"Invalid authority {authority!r} on operation {op_id!r}.",
                )
            )

        # Native expected_args and operation input_values are preserved verbatim (never dereferenced)
        expected_args = copy.deepcopy(op.get("expected_args", {}))
        input_values = copy.deepcopy(op.get("input_values", {}))

        raw_result = copy.deepcopy(op.get("result"))
        result_projection: dict[str, Any]

        if raw_result is None:
            result_projection = {
                "kind": "no_result",
                "has_artifact": False,
                "artifact_ref": None,
                "value": None,
            }
        elif isinstance(raw_result, Mapping) and raw_result.get("result_kind") == "artifact":
            art_id = str(raw_result.get("artifact_id", ""))
            art_epoch = raw_result.get("epoch", coherence.artifact_epoch)
            art_ref = EntityRef(namespace="artifact", entity_id=art_id, epoch=art_epoch)
            issues.extend(art_ref.validate(f"{ptr}/result/artifact_ref"))
            if isinstance(art_epoch, int) and art_epoch != coherence.artifact_epoch:
                issues.append(
                    ValidationIssue(
                        code="stale_generation",
                        pointer=f"{ptr}/result/epoch",
                        message=f"Operation {op_id!r} artifact epoch ({art_epoch}) != {coherence.artifact_epoch}.",
                    )
                )
            result_projection = {
                "kind": "artifact",
                "has_artifact": True,
                "artifact_ref": art_ref.to_dict(),
                "value": copy.deepcopy(raw_result.get("payload")),
            }
        elif isinstance(raw_result, Mapping) and raw_result.get("result_kind") == "scalar":
            result_projection = {
                "kind": "no_artifact",
                "has_artifact": False,
                "artifact_ref": None,
                "value": copy.deepcopy(raw_result.get("payload")),
            }
        else:
            # Unknown result structure -> keep raw fallback without guessing
            result_projection = {
                "kind": "raw_fallback",
                "has_artifact": False,
                "artifact_ref": None,
                "raw_result": raw_result,
            }

        compiled_ops.append({
            "op_id": op_id,
            "op_type": op_type,
            "authority": authority,
            "expected_args": expected_args,
            "input_values": input_values,
            "result": result_projection,
        })

    return compiled_ops


def compile_context_snapshot(
    canonical_state: Mapping[str, Any],
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Compile a pure, deterministic context snapshot from canonical state copies.

    Does not mutate `canonical_state` or any nested structure inside it.
    """
    state_copy = copy.deepcopy(dict(canonical_state))
    issues: list[ValidationIssue] = []

    raw_coherence = state_copy.get("coherence", {})
    selection_set_flag = raw_coherence.get("selection_set", False)
    raw_selected_ids = raw_coherence.get("selected_ids", [])

    coherence = CoherenceMetadata(
        artifact_epoch=raw_coherence.get("artifact_epoch", 0),
        notebook_epoch=raw_coherence.get("notebook_epoch", 0),
        selection_set=selection_set_flag,
        selected_ids=tuple(str(x) for x in raw_selected_ids) if isinstance(raw_selected_ids, Sequence) else (),
    )
    issues.extend(coherence.validate())

    # Single canonical representation for proposal (separate from receipts/proofs)
    raw_proposal = state_copy.get("proposal")
    proposal_projection: dict[str, Any] | None = None
    if raw_proposal is not None:
        proposal_copy = copy.deepcopy(dict(raw_proposal))
        # Strip any accidentally embedded receipts/proofs to enforce separation
        if "receipts" in proposal_copy or "proofs" in proposal_copy:
            issues.append(
                ValidationIssue(
                    code="MixedProposalAndReceipts",
                    pointer="/proposal",
                    message="Proposal must not embed actual receipts or proofs; keep separate.",
                )
            )
            proposal_copy.pop("receipts", None)
            proposal_copy.pop("proofs", None)

        prop_authority = str(proposal_copy.get("authority", "system"))
        if prop_authority not in VALID_AUTHORITIES:
            issues.append(
                ValidationIssue(
                    code="invalid_proposal_authority",
                    pointer="/proposal/authority",
                    message=f"Invalid proposal authority: {prop_authority!r}",
                )
            )
        proposal_projection = {
            "proposal_id": str(proposal_copy.get("proposal_id", "prop_0")),
            "authority": prop_authority,
            "expected_args": copy.deepcopy(proposal_copy.get("expected_args", {})),
            "payload": copy.deepcopy(proposal_copy.get("payload", {})),
        }

    contract_export, progress = _compile_contract_and_progress(
        raw_contract=state_copy.get("contract"),
        reconciler_assessment=state_copy.get("reconciler_assessment"),
        actual_receipts=state_copy.get("receipts", []),
        actual_proofs=state_copy.get("proofs", []),
        lifecycle_phase=str(state_copy.get("lifecycle_phase", "active")),
        issues=issues,
    )

    notes, generated_quote_refs, quotes = _compile_notes_and_quotes(
        raw_notes=state_copy.get("notes", []),
        raw_quotes=state_copy.get("quotes", []),
        coherence=coherence,
        issues=issues,
    )

    operations = _compile_operations(
        raw_operations=state_copy.get("operations", []),
        coherence=coherence,
        issues=issues,
    )

    # Decode $value_ref ONLY in declared typed projection slots
    registry = state_copy.get("entity_registry", {})
    raw_slots = state_copy.get("projection_slots", {})
    compiled_slots: dict[str, Any] = {}
    if isinstance(raw_slots, Mapping):
        for slot_name, slot_spec in raw_slots.items():
            compiled_slots[str(slot_name)] = _resolve_typed_slot_value(
                slot_name=str(slot_name),
                raw_slot_spec=slot_spec,
                registry=registry,
                coherence=coherence,
                issues=issues,
            )

    # Preserve arbitrary user data untouched (fake $value_ref inside user_payload is NOT decoded)
    passthrough_user_data = copy.deepcopy(state_copy.get("user_payload", {}))

    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "coherence": coherence.to_dict(),
        "proposal": proposal_projection,
        "contract": contract_export,
        "progress": progress,
        "notes": notes,
        "quote_refs": generated_quote_refs,
        "quotes": quotes,
        "operations": operations,
        "projection_slots": compiled_slots,
        "user_payload": passthrough_user_data,
        "validation": {
            "is_clean": len(issues) == 0,
            "issue_count": len(issues),
            "issues": [issue.to_dict() for issue in issues],
        },
    }

    if strict and issues:
        raise SnapshotCompilationError(
            f"Context snapshot compilation failed with {len(issues)} issue(s): "
            + "; ".join(f"{i.code} at {i.pointer}" for i in issues)
        )

    return snapshot

