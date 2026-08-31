#!/usr/bin/env python3
"""Host-receipt and real command-evidence boundary for the local workflow."""

import copy
import hashlib
import json
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from adw_core import AdwError, GATE_REQUIREMENTS, approved_test_design_command, canonical_json, read_consistent_snapshot, record_evidence, validate_tdd_evidence_selection, verify_artifact


RECEIPT_FIELDS = {
    "schema", "id", "kind", "host", "role", "session_id", "turn_id", "event_id",
    "cwd", "created_at", "claim", "artifact_sha256", "receipt_hash",
}
RECEIPT_KINDS = {"approval_request", "human_approval", "lead_call", "judge_output"}
RECEIPT_ROLES = {"developer", "ticket_owner", "lead_agent", "judge_agent"}
SECRET_PATTERN = re.compile(
    r"(?i)(authorization\s*:|bearer\s+[A-Za-z0-9._~+/=-]+|password\s*[=:]|secret\s*[=:]|token\s*[=:]|cookie\s*:)",
)
MAX_COMMAND_OUTPUT = 128 * 1024


def default_receipt_root():
    return Path.home() / ".codex" / "agentic-development-workflow" / "receipts"


def cli_argv_sha256(script_path, argv):
    normalized = [str(Path(script_path).resolve())] + list(argv)
    return _sha256(canonical_json(normalized))


def _sha256(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _utc_text(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _safe_text(value, name, limit=256):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(char) < 32 for char in value):
        raise AdwError(7, "authority_required", "%s is invalid" % name)


def _prepare_root(root):
    root = Path(root)
    for directory in (root, root / "records", root / "artifacts"):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise AdwError(7, "authority_required", "receipt store is unsafe")
        os.chmod(str(directory), 0o700)
    return root


def _write_new(path, data):
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _read_regular(path, limit=MAX_COMMAND_OUTPUT * 2, private=False):
    path = Path(path)
    try:
        metadata = path.lstat()
    except OSError as error:
        raise AdwError(7, "authority_required", "receipt material is unavailable: %s" % error)
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_size > limit:
        raise AdwError(7, "authority_required", "receipt material is unsafe")
    descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if private and stat.S_IMODE(opened.st_mode) & 0o077:
            raise AdwError(7, "authority_required", "receipt material permissions are unsafe")
        data = b""
        while len(data) <= limit:
            chunk = os.read(descriptor, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data += chunk
    finally:
        os.close(descriptor)
    if len(data) > limit:
        raise AdwError(7, "authority_required", "receipt material exceeds its size limit")
    return data


def create_receipt(root, kind, role, claim, artifact_bytes, session_id, turn_id, event_id, cwd, now=None):
    """Create one immutable host receipt and its exact safe artifact."""

    if kind not in RECEIPT_KINDS or role not in RECEIPT_ROLES or not isinstance(claim, dict) or not isinstance(artifact_bytes, bytes):
        raise AdwError(7, "authority_required", "receipt claim is invalid")
    for value, name in ((session_id, "session_id"), (turn_id, "turn_id"), (event_id, "event_id"), (cwd, "cwd")):
        _safe_text(value, name, 1024 if name == "cwd" else 256)
    root = _prepare_root(root)
    created_at = _utc_text(now or datetime.now(timezone.utc))
    base = {
        "schema": 1, "kind": kind, "host": "codex", "role": role,
        "session_id": session_id, "turn_id": turn_id, "event_id": event_id,
        "cwd": cwd, "created_at": created_at, "claim": copy.deepcopy(claim),
        "artifact_sha256": _sha256(artifact_bytes),
    }
    receipt_id = kind + "-" + hashlib.sha256(canonical_json(base)).hexdigest()[:24]
    record = dict(base, id=receipt_id)
    record["receipt_hash"] = _sha256(canonical_json(record))
    record_path = root / "records" / (receipt_id + ".json")
    artifact_path = root / "artifacts" / (receipt_id + ".json")
    encoded = canonical_json(record)
    try:
        _write_new(artifact_path, artifact_bytes)
        _write_new(record_path, encoded)
    except FileExistsError:
        if _read_regular(record_path, private=True) != encoded or _read_regular(artifact_path, private=True) != artifact_bytes:
            raise AdwError(7, "authority_required", "receipt ID collision is inconsistent")
    return dict(record, ref="receipt:" + receipt_id)


def load_receipt(root, reference):
    """Load and verify one immutable host receipt by opaque reference."""

    if not isinstance(reference, str) or not re.fullmatch(r"receipt:[a-z_]+-[0-9a-f]{24}", reference):
        raise AdwError(7, "authority_required", "producer proof reference is invalid")
    root = Path(root)
    receipt_id = reference.split(":", 1)[1]
    try:
        record = json.loads(_read_regular(root / "records" / (receipt_id + ".json"), private=True).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise AdwError(7, "authority_required", "receipt is invalid: %s" % error)
    if not isinstance(record, dict) or set(record) != RECEIPT_FIELDS or record.get("schema") != 1 or record.get("id") != receipt_id:
        raise AdwError(7, "authority_required", "receipt schema is invalid")
    supplied_hash = record.get("receipt_hash")
    unsigned = dict(record)
    unsigned.pop("receipt_hash", None)
    if supplied_hash != _sha256(canonical_json(unsigned)):
        raise AdwError(7, "authority_required", "receipt integrity is invalid")
    if record.get("kind") not in RECEIPT_KINDS or record.get("role") not in RECEIPT_ROLES or record.get("host") != "codex":
        raise AdwError(7, "authority_required", "receipt authority is invalid")
    for field in ("session_id", "turn_id", "event_id", "cwd", "created_at"):
        _safe_text(record.get(field), "receipt.%s" % field, 1024 if field == "cwd" else 256)
    if not isinstance(record.get("claim"), dict):
        raise AdwError(7, "authority_required", "receipt claim is invalid")
    artifact = _read_regular(root / "artifacts" / (receipt_id + ".json"), private=True)
    if _sha256(artifact) != record.get("artifact_sha256"):
        raise AdwError(7, "authority_required", "receipt artifact integrity is invalid")
    return dict(record, ref=reference)


def read_receipt_artifact(root, receipt):
    if not isinstance(receipt, dict) or not isinstance(receipt.get("id"), str):
        raise AdwError(7, "authority_required", "receipt is invalid")
    artifact = _read_regular(Path(root) / "artifacts" / (receipt["id"] + ".json"), private=True)
    if _sha256(artifact) != receipt.get("artifact_sha256"):
        raise AdwError(7, "authority_required", "receipt artifact integrity is invalid")
    return artifact


def read_proposal_file(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise AdwError(2, "unsafe_path", "evidence proposal path is unsafe")
    try:
        value = json.loads(_read_regular(path, 65536).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise AdwError(2, "invalid_input", "evidence proposal must be strict JSON")
    if not isinstance(value, dict):
        raise AdwError(2, "invalid_input", "evidence proposal must be an object")
    return value


def find_lead_call_receipt(root, script_path, argv, cwd, work_item, now=None, max_age_seconds=30):
    """Resolve the newest fresh PreToolUse receipt for this exact public CLI call."""

    root = Path(root)
    expected_argv = cli_argv_sha256(script_path, argv)
    current = now or datetime.now(timezone.utc)
    matches = []
    records = root / "records"
    if records.is_dir() and not records.is_symlink():
        for path in records.glob("lead_call-*.json"):
            try:
                receipt = load_receipt(root, "receipt:" + path.stem)
                created = datetime.fromisoformat(receipt["created_at"].replace("Z", "+00:00"))
            except (AdwError, ValueError):
                continue
            age = (current - created).total_seconds()
            command_cwd = receipt["claim"].get("command_cwd", receipt["cwd"])
            if (
                0 <= age <= max_age_seconds and command_cwd == str(Path(cwd))
                and receipt["claim"].get("work_item") == work_item
                and receipt["claim"].get("argv_sha256") == expected_argv
            ):
                matches.append((created, receipt))
    if not matches:
        raise AdwError(7, "authority_required", "fresh host lead-call receipt is missing")
    matches.sort(key=lambda value: value[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        raise AdwError(7, "authority_required", "host lead-call receipt is ambiguous")
    return matches[0][1]


def _receipts_of_kind(root, kind):
    records = Path(root) / "records"
    if not records.is_dir() or records.is_symlink():
        return []
    receipts = []
    for path in records.glob(kind + "-*.json"):
        try:
            receipts.append(load_receipt(root, "receipt:" + path.stem))
        except AdwError:
            continue
    return receipts


def find_specification_approval_receipt(root, work_item, revision, role):
    matches = [
        receipt for receipt in _receipts_of_kind(root, "human_approval")
        if receipt["role"] == role and receipt["claim"] == {
            "work_item": work_item, "decision": "specification_approved",
            "revision": revision, "role": role,
        }
    ]
    if not matches:
        return None
    matches.sort(key=lambda receipt: (receipt["created_at"], receipt["id"]), reverse=True)
    return matches[0]


def _current_specification(snapshot, work_item):
    if snapshot.state["state"] != "SPECIFY" or snapshot.state["review_pass"] is not None:
        raise AdwError(4, "invalid_state", "specification approval is available only in SPECIFY")
    revision = snapshot.state["current_revisions"]["specification"]
    matches = [
        entry for entry in snapshot.state["revision_history"]
        if entry.get("domain") == "specification" and entry.get("id") == revision
    ]
    if not revision or len(matches) != 1:
        raise AdwError(4, "incomplete_specification", "a current immutable specification package is required")
    entry = matches[0]
    verify_artifact(work_item, entry["source_ref"], entry["fingerprint"])
    return revision, entry


def _approval_context(work_item, role, expected_sequence, expected_head):
    if role not in {"developer", "ticket_owner"}:
        raise AdwError(2, "invalid_input", "approval role is invalid")
    snapshot = read_consistent_snapshot(work_item)
    if snapshot.audit["sequence"] != expected_sequence or snapshot.audit["head"] != expected_head:
        raise AdwError(5, "stale_snapshot", "expected audit identity is stale")
    revision, entry = _current_specification(snapshot, work_item)
    claim = {
        "work_item": snapshot.state["work_item"], "decision": "specification_approved",
        "revision": revision, "role": role, "work_item_path": str(Path(work_item).resolve()),
        "audit_sequence": snapshot.audit["sequence"], "audit_head": snapshot.audit["head"],
        "artifact_ref": entry["source_ref"], "artifact_fingerprint": entry["fingerprint"],
    }
    return snapshot, revision, entry, claim


def create_specification_approval_request(work_item, role, root, expected_sequence, expected_head,
                                          session_id, turn_id, event_id, cwd):
    """Create the host-owned request that makes one simple human reply unambiguous."""

    _, _, _, claim = _approval_context(
        work_item, role, expected_sequence, expected_head,
    )
    return create_receipt(
        root, "approval_request", "lead_agent", claim, canonical_json(claim),
        session_id, turn_id, event_id, cwd,
    )


def prepare_specification_approval(work_item, role, lead, root, expected_sequence, expected_head):
    """Verify the host prepared approval before the human is asked."""

    snapshot, revision, entry, claim = _approval_context(
        work_item, role, expected_sequence, expected_head,
    )
    if (
        lead["kind"] != "lead_call" or lead["role"] != "lead_agent"
        or lead["claim"].get("subcommand") != "prepare-approval"
        or lead["claim"].get("work_item") != snapshot.state["work_item"]
    ):
        raise AdwError(7, "authority_required", "prepare-approval requires its exact host lead-call receipt")
    existing = find_specification_approval_receipt(root, snapshot.state["work_item"], revision, role)
    if existing is not None:
        return {
            "work_item": snapshot.state["work_item"], "state": snapshot.state["state"],
            "status": "approval_already_captured", "revision": revision,
            "artifact_ref": entry["source_ref"],
            "artifact_path": str(Path(work_item).resolve() / entry["source_ref"]),
            "human_approval_ref": existing["ref"],
        }
    requests = [
        receipt for receipt in _receipts_of_kind(root, "approval_request")
        if receipt["role"] == "lead_agent" and receipt["claim"] == claim
        and all(receipt[field] == lead[field] for field in ("session_id", "turn_id", "event_id", "cwd"))
    ]
    if len(requests) != 1:
        raise AdwError(7, "authority_required", "host approval-request receipt is missing or ambiguous")
    request = requests[0]
    return {
        "work_item": snapshot.state["work_item"], "state": snapshot.state["state"],
        "status": "awaiting_human_approval", "revision": revision,
        "artifact_ref": entry["source_ref"],
        "artifact_path": str(Path(work_item).resolve() / entry["source_ref"]),
        "approval_request_ref": request["ref"],
        "reply": "I approve",
    }


def find_current_approval_request(root, session_id, cwd):
    """Resolve one current prepared approval for a natural-language user reply."""

    candidates = []
    for receipt in _receipts_of_kind(root, "approval_request"):
        claim = receipt["claim"]
        if receipt["session_id"] != session_id or receipt["cwd"] != cwd:
            continue
        try:
            item = Path(claim["work_item_path"])
            snapshot = read_consistent_snapshot(item)
            revision, entry = _current_specification(snapshot, item)
        except (AdwError, KeyError, TypeError):
            continue
        expected = {
            "work_item": snapshot.state["work_item"], "decision": "specification_approved",
            "revision": revision, "role": claim.get("role"), "work_item_path": str(item.resolve()),
            "audit_sequence": snapshot.audit["sequence"], "audit_head": snapshot.audit["head"],
            "artifact_ref": entry["source_ref"], "artifact_fingerprint": entry["fingerprint"],
        }
        if claim == expected and claim["role"] in {"developer", "ticket_owner"}:
            candidates.append(receipt)
    identities = {
        (receipt["claim"]["work_item_path"], receipt["claim"]["revision"], receipt["claim"]["role"])
        for receipt in candidates
    }
    if len(identities) != 1:
        raise AdwError(7, "authority_required", "one current prepared workflow approval is required")
    candidates.sort(key=lambda receipt: (receipt["created_at"], receipt["id"]), reverse=True)
    return candidates[0]


def _verify_lead_receipt(lead, proposal, work_item):
    if lead["kind"] != "lead_call" or lead["role"] != "lead_agent":
        raise AdwError(7, "authority_required", "lead-call receipt is required")
    expected = _sha256(canonical_json(proposal))
    if lead["claim"].get("work_item") != work_item or lead["claim"].get("proposal_sha256") != expected:
        raise AdwError(7, "authority_required", "lead-call receipt does not bind this proposal")


def _verify_producer_receipt(receipt, proposal, artifact_bytes):
    if receipt["ref"] != proposal.get("producer_proof_ref") or receipt["role"] != proposal.get("producer_role"):
        raise AdwError(7, "authority_required", "producer receipt role or reference does not match")
    if receipt["artifact_sha256"] != _sha256(artifact_bytes):
        raise AdwError(7, "authority_required", "producer receipt does not bind the artifact")
    claim = receipt["claim"]
    if claim.get("work_item") != proposal.get("work_item") or claim.get("decision") != proposal.get("decision"):
        raise AdwError(7, "authority_required", "producer receipt does not bind the work item decision")
    if receipt["kind"] == "human_approval":
        if proposal.get("producer_ref") != "codex-local-human:" + receipt["session_id"]:
            raise AdwError(7, "authority_required", "human producer reference is invalid")
        if claim.get("revision") != proposal.get("input_revisions", {}).get("specification"):
            raise AdwError(7, "authority_required", "human approval does not bind the specification revision")
        try:
            artifact = json.loads(artifact_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            raise AdwError(7, "authority_required", "human approval receipt artifact is invalid")
        if (
            not isinstance(artifact, dict)
            or set(artifact) != {"approval_request_ref", "human_message", "normalized_claim"}
            or artifact.get("normalized_claim") != claim
            or not isinstance(artifact.get("approval_request_ref"), str)
            or not artifact["approval_request_ref"].startswith("receipt:approval_request-")
            or not isinstance(artifact.get("human_message"), str)
            or artifact["human_message"].strip().casefold() != "i approve"
        ):
            raise AdwError(7, "authority_required", "human approval must be the prepared natural-language approval")
    elif receipt["kind"] == "judge_output":
        for field in ("state", "result_status", "supports", "input_revisions", "findings"):
            if claim.get(field) != proposal.get(field):
                raise AdwError(7, "authority_required", "judge receipt does not bind %s" % field)
    else:
        raise AdwError(7, "authority_required", "producer receipt kind cannot authorize this evidence")


def _ensure_evidence_artifact_parent(work_item, artifact_ref):
    relative = Path(artifact_ref)
    if relative.parts[:2] != ("artifacts", "evidence") or len(relative.parts) != 3:
        raise AdwError(2, "unsafe_path", "public evidence artifacts must use artifacts/evidence/<file>")
    root = Path(work_item) / "artifacts"
    target = root / "evidence"
    if root.is_symlink() or not root.is_dir():
        raise AdwError(2, "unsafe_path", "work-item artifact root is unsafe")
    try:
        target.mkdir(mode=0o700)
    except FileExistsError:
        pass
    if target.is_symlink() or not target.is_dir():
        raise AdwError(2, "unsafe_path", "evidence artifact directory is unsafe")


def record_evidence_from_receipts(work_item, proposal, producer_reference, lead_reference, receipt_root,
                                  expected_sequence, expected_head, now=None):
    """Record public evidence only when host receipts bind producer, lead, and artifact."""

    if not isinstance(proposal, dict):
        raise AdwError(2, "invalid_input", "evidence proposal must be an object")
    producer = load_receipt(receipt_root, producer_reference)
    lead = load_receipt(receipt_root, lead_reference)
    artifact_bytes = read_receipt_artifact(receipt_root, producer)
    _verify_lead_receipt(lead, proposal, proposal.get("work_item"))
    _verify_producer_receipt(producer, proposal, artifact_bytes)
    _ensure_evidence_artifact_parent(work_item, proposal.get("artifact_ref"))
    lead_ref = "codex:%s:%s:lead" % (lead["session_id"], lead["turn_id"])
    request_id = "codex:" + lead["event_id"]
    return record_evidence(
        work_item, copy.deepcopy(proposal), artifact_bytes, lambda candidate: True,
        request_id, expected_sequence, expected_head, lead_ref, now=now,
    )


def record_specification_approval(work_item, role, lead, receipt_root,
                                  expected_sequence, expected_head, now=None):
    """Record the current human approval without an agent-written proposal file."""

    snapshot = read_consistent_snapshot(work_item)
    if snapshot.audit["sequence"] != expected_sequence or snapshot.audit["head"] != expected_head:
        raise AdwError(5, "stale_snapshot", "expected audit identity is stale")
    revision, _ = _current_specification(snapshot, work_item)
    producer = find_specification_approval_receipt(
        receipt_root, snapshot.state["work_item"], revision, role,
    )
    if producer is None:
        raise AdwError(7, "authority_required", "current human approval receipt is missing")
    if (
        lead.get("kind") != "lead_call" or lead.get("role") != "lead_agent"
        or lead.get("claim", {}).get("subcommand") != "record-approval"
        or lead.get("claim", {}).get("work_item") != snapshot.state["work_item"]
    ):
        raise AdwError(7, "authority_required", "exact record-approval call receipt is required")

    artifact_bytes = read_receipt_artifact(receipt_root, producer)
    suffix = producer["id"].rsplit("-", 1)[-1][:12]
    evidence_id = "E-APPROVAL-" + suffix
    proposal = {
        "id": evidence_id,
        "type": "approval_decision",
        "work_item": snapshot.state["work_item"],
        "state": "SPECIFY",
        "review_pass": None,
        "observed_at": producer["created_at"],
        "result_status": "pass",
        "validity_status": "current",
        "producer_role": role,
        "producer_ref": "codex-local-human:" + producer["session_id"],
        "producer_proof_ref": producer["ref"],
        "source_ref": "approval:" + producer["event_id"],
        "artifact_ref": "artifacts/evidence/%s.json" % evidence_id,
        "integrity_ref": producer["artifact_sha256"],
        "input_revisions": {"specification": revision},
        "supports": [],
        "historical_supports": [],
        "revision_transition": None,
        "supersedes": [],
        "invalidation_reason": None,
        "gate": "specification_approval",
        "decision": "specification_approved",
    }
    _verify_producer_receipt(producer, proposal, artifact_bytes)
    _ensure_evidence_artifact_parent(work_item, proposal["artifact_ref"])
    return record_evidence(
        work_item, proposal, artifact_bytes, lambda candidate: True,
        "codex:" + lead["event_id"], expected_sequence, expected_head,
        "codex:%s:%s:lead" % (lead["session_id"], lead["turn_id"]), now=now,
    )


def record_lead_gate_decision(work_item, evidence_id, gate, supports, lead,
                              expected_sequence, expected_head, historical_supports=None,
                              supersedes=None, now=None):
    """Record one lead-owned gate decision bound to its exact host-observed CLI call."""

    snapshot = read_consistent_snapshot(work_item)
    requirement = GATE_REQUIREMENTS.get(gate)
    if requirement is None or requirement[2] != {"lead_agent"}:
        raise AdwError(2, "invalid_input", "gate is not owned by the lead agent")
    evidence_type, decision, _, state, review_pass, required_revisions = requirement
    if (snapshot.state["state"], snapshot.state["review_pass"]) != (state, review_pass):
        raise AdwError(4, "invalid_state", "lead decision does not match the current state")
    if (
        lead.get("kind") != "lead_call" or lead.get("role") != "lead_agent"
        or lead.get("claim", {}).get("subcommand") != "record-lead-decision"
        or lead.get("claim", {}).get("work_item") != snapshot.state["work_item"]
    ):
        raise AdwError(7, "authority_required", "exact lead-decision call receipt is required")
    supports = list(supports or [])
    historical_supports = list(historical_supports or [])
    if supersedes is not None and (not isinstance(supersedes, str) or not supersedes):
        raise AdwError(2, "invalid_input", "gate supersession must name one prior gate evidence ID")
    prior_gate = snapshot.state["gate_evidence"][gate]
    if prior_gate != supersedes:
        raise AdwError(4, "invalid_input", "gate replacement must explicitly supersede the current gate")
    if gate == "tdd_pass":
        validate_tdd_evidence_selection(snapshot, work_item, supports, historical_supports)
    elif historical_supports:
        raise AdwError(2, "invalid_input", "historical support is accepted only for the TDD gate")
    input_revisions = {
        domain: snapshot.state["current_revisions"][domain]
        for domain in sorted(required_revisions)
    }
    lead_ref = "codex:%s:%s:lead" % (lead["session_id"], lead["turn_id"])
    artifact = canonical_json({
        "decision": decision,
        "evidence_id": evidence_id,
        "gate": gate,
        "input_revisions": input_revisions,
        "producer_proof_ref": lead["ref"],
        "result_status": "pass",
        "review_pass": review_pass,
        "state": state,
        "supports": supports,
        "historical_supports": historical_supports,
        "work_item": snapshot.state["work_item"],
    })
    record = {
        "id": evidence_id,
        "type": evidence_type,
        "work_item": snapshot.state["work_item"],
        "state": state,
        "review_pass": review_pass,
        "observed_at": lead["created_at"],
        "result_status": "pass",
        "validity_status": "current",
        "producer_role": "lead_agent",
        "producer_ref": lead_ref,
        "producer_proof_ref": lead["ref"],
        "source_ref": "lead-decision:" + gate,
        "artifact_ref": "artifacts/evidence/%s.json" % evidence_id,
        "integrity_ref": _sha256(artifact),
        "input_revisions": input_revisions,
        "supports": supports,
        "historical_supports": historical_supports,
        "revision_transition": None,
        "supersedes": [supersedes] if supersedes else [],
        "invalidation_reason": None,
        "gate": gate,
        "decision": decision,
    }
    _ensure_evidence_artifact_parent(work_item, record["artifact_ref"])
    return record_evidence(
        work_item, record, artifact,
        lambda candidate: (
            candidate.get("producer_role") == "lead_agent"
            and candidate.get("producer_proof_ref") == lead["ref"]
            and candidate.get("producer_ref") == lead_ref
        ),
        "codex:" + lead["event_id"], expected_sequence, expected_head, lead_ref, now=now,
    )


def _reject_secret_material(text, name):
    if SECRET_PATTERN.search(text):
        raise AdwError(7, "unsafe_evidence", "%s contains secret-like material" % name)


def run_evidence_command(work_item, command, cwd, evidence_id, source_ref, supports, expected_exit_codes,
                         request_id, lead_run_ref, expected_sequence, expected_head,
                         timeout_seconds=600, now=None):
    """Execute one real argv command without a shell and atomically record its actual result."""

    if not isinstance(command, list) or not command or any(not isinstance(value, str) or not value for value in command):
        raise AdwError(2, "invalid_input", "command must be a non-empty argv array")
    if not isinstance(expected_exit_codes, list) or not expected_exit_codes or any(isinstance(code, bool) or not isinstance(code, int) for code in expected_exit_codes):
        raise AdwError(2, "invalid_input", "expected exit codes are invalid")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 1800:
        raise AdwError(2, "invalid_input", "command timeout is invalid")
    cwd = Path(cwd)
    snapshot = read_consistent_snapshot(work_item)
    configured_repository = Path(snapshot.state["repository"])
    matches_repository = (
        cwd.resolve(strict=False) == configured_repository.resolve(strict=False)
        if configured_repository.is_absolute()
        else cwd.name == snapshot.state["repository"]
    )
    if not cwd.is_absolute() or cwd.is_symlink() or not cwd.is_dir() or not matches_repository:
        raise AdwError(2, "unsafe_path", "command working directory must be the configured repository root")
    approved = approved_test_design_command(snapshot, work_item, source_ref)
    if (
        command != approved["argv"]
        or sorted(set(expected_exit_codes)) != approved["expected_exit_codes"]
        or timeout_seconds != approved["timeout_seconds"]
    ):
        raise AdwError(2, "invalid_input", "evidence command does not exactly match the current test-design registry")
    for argument in command:
        _reject_secret_material(argument, "command argument")
    try:
        completed = subprocess.run(
            command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout_seconds, check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise AdwError(7, "command_unavailable", "evidence command could not complete: %s" % error)
    if len(completed.stdout) > MAX_COMMAND_OUTPUT or len(completed.stderr) > MAX_COMMAND_OUTPUT:
        raise AdwError(7, "unsafe_evidence", "command output exceeds the evidence limit")
    stdout = completed.stdout.decode("utf-8", "replace")
    stderr = completed.stderr.decode("utf-8", "replace")
    _reject_secret_material(stdout, "command stdout")
    _reject_secret_material(stderr, "command stderr")
    artifact = canonical_json({
        "schema": 1, "argv": command, "cwd": str(cwd), "exit_code": completed.returncode,
        "expected_exit_codes": sorted(set(expected_exit_codes)), "stdout": stdout, "stderr": stderr,
    })
    proof = "execution:" + hashlib.sha256(artifact).hexdigest()
    observed_at = _utc_text(now or datetime.now(timezone.utc))
    record = {
        "id": evidence_id, "type": "command_result", "work_item": snapshot.state["work_item"],
        "state": snapshot.state["state"], "review_pass": snapshot.state["review_pass"],
        "observed_at": observed_at, "result_status": "pass" if completed.returncode in expected_exit_codes else "fail",
        "validity_status": "current", "producer_role": "qa_tool", "producer_ref": "command:" + source_ref,
        "producer_proof_ref": proof, "source_ref": source_ref,
        "artifact_ref": "artifacts/evidence/%s.json" % evidence_id,
        "integrity_ref": _sha256(artifact),
        "input_revisions": {name: value for name, value in snapshot.state["current_revisions"].items() if value is not None},
        "supports": list(supports), "historical_supports": [], "revision_transition": None,
        "supersedes": [], "invalidation_reason": None,
    }
    _ensure_evidence_artifact_parent(work_item, record["artifact_ref"])
    return record_evidence(
        work_item, record, artifact,
        lambda candidate: candidate.get("producer_proof_ref") == proof and candidate.get("integrity_ref") == _sha256(artifact),
        request_id, expected_sequence, expected_head, lead_run_ref, now=now,
    )
