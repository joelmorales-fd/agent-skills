#!/usr/bin/env python3
"""Internal standard-library foundation for the Agentic Development Workflow guardrail."""

import copy
import hashlib
import json
import os
import re
import secrets
import socket
import stat
import subprocess
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import fcntl


STATE_FIELDS = {
    "work_item", "repository", "state", "review_pass", "blocked_from_state",
    "blocked_from_review_pass", "resume_state", "resume_review_pass", "owner",
    "required_evidence_ids", "write_policy", "audit", "current_revisions",
    "revision_history", "gate_evidence", "transition_history", "loop_policy",
    "blocker_ids", "exception_ids",
}
EVIDENCE_FIELDS = {"work_item", "audit", "evidence_index"}
AUDIT_FIELDS = {"sequence", "head", "last_transaction_id", "last_request_id"}
REVISION_FIELDS = {"specification", "test_design", "change", "configuration", "environment"}
GATE_FIELDS = {
    "specification_approval", "test_design_pass", "tdd_pass", "first_review",
    "local_qa_pass", "mutation_decision", "final_review",
}
STATES = {
    "SPECIFY", "TEST_DESIGN", "TDD", "CODE_QUALITY_GATE", "LOWER_ENV_VERIFY",
    "MUTATION_GATE", "DELIVERY_GATE", "COMPLETE", "BLOCKED",
}
EVIDENCE_TYPES = {
    "approval_decision", "gate_decision", "artifact_snapshot", "command_result", "tdd_cycle",
    "review_finding", "finding_resolution", "root_cause_record", "correction_attempt",
    "local_qa_result", "mutation_result", "blocker", "blocker_resolution", "exception_decision",
}
PRODUCER_ROLES = {
    "developer", "ticket_owner", "lead_agent", "specification_agent", "test_design_agent",
    "tdd_agent", "judge_agent", "qa_tool", "runner", "mutation_tool",
}
GATE_REQUIREMENTS = {
    "specification_approval": ("approval_decision", "specification_approved", {"developer", "ticket_owner"}, "SPECIFY", None, {"specification"}),
    "test_design_pass": ("gate_decision", "test_design_accepted", {"lead_agent"}, "TEST_DESIGN", None, {"specification", "test_design", "configuration"}),
    "tdd_pass": ("gate_decision", "tdd_accepted", {"lead_agent"}, "TDD", None, {"specification", "test_design", "change", "configuration"}),
    "first_review": ("gate_decision", "continue_to_local_qa", {"judge_agent"}, "CODE_QUALITY_GATE", None, {"specification", "test_design", "change", "configuration"}),
    "local_qa_pass": ("gate_decision", "local_qa_accepted", {"lead_agent"}, "LOWER_ENV_VERIFY", None, set(REVISION_FIELDS)),
    "mutation_decision": ("gate_decision", "mutation_accepted", {"lead_agent"}, "MUTATION_GATE", None, {"specification", "test_design", "change", "configuration"}),
    "final_review": ("gate_decision", "approved", {"judge_agent"}, "DELIVERY_GATE", None, set(REVISION_FIELDS)),
}
ROUTE_DECISION_ROLES = {
    "return_to_specify": {"lead_agent", "judge_agent"},
    "return_to_test_design": {"lead_agent", "judge_agent"},
    "return_to_tdd": {"lead_agent", "judge_agent"},
    "blocked": {"lead_agent", "judge_agent"},
    "resume_accepted": {"lead_agent"},
}
SECRET_EVIDENCE_PATTERN = re.compile(
    r"(?i)(authorization\s*:|bearer\s+[A-Za-z0-9._~+/=-]+|password\s*[=:]|secret\s*[=:]|token\s*[=:]|cookie\s*:)",
)


class AdwError(Exception):
    """Expected fail-closed error with a stable command-contract exit code."""

    def __init__(self, code: int, kind: str, message: str):
        super().__init__(message)
        self.code = code
        self.kind = kind


class InjectedCrash(Exception):
    """Test-only process-stop signal used to verify durable crash boundaries."""


def _strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key: %s" % key)
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("non-finite JSON number: %s" % value)


def _reject_floats(value: Any) -> None:
    if isinstance(value, float):
        raise ValueError("floating-point values are not supported")
    if isinstance(value, dict):
        for item in value.values():
            _reject_floats(item)
    elif isinstance(value, list):
        for item in value:
            _reject_floats(item)


def _normalize_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise AdwError(4, "invalid_control_block", "floating-point values are not supported")
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFC", value)
        try:
            normalized.encode("utf-8")
        except UnicodeEncodeError:
            raise AdwError(4, "invalid_control_block", "JSON strings must be valid UTF-8 Unicode")
        return normalized
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise AdwError(4, "invalid_control_block", "JSON object keys must be strings")
            clean_key = _normalize_json(key)
            if clean_key in normalized:
                raise AdwError(4, "invalid_control_block", "duplicate key after NFC normalization")
            normalized[clean_key] = _normalize_json(item)
        return normalized
    raise AdwError(4, "invalid_control_block", "unsupported JSON value type")


def canonical_json(value: Any) -> bytes:
    """Return transaction-schema-1 canonical JSON bytes."""

    normalized = _normalize_json(value)
    return (json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n").encode("utf-8")


def _invalid(message: str) -> None:
    raise AdwError(4, "invalid_control_block", message)


def _unsafe(message: str) -> None:
    raise AdwError(2, "unsafe_path", message)


def _path_identifier(value: Any, name: str) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or not value[0].isalnum()
        or any(not (character.isalnum() or character in "._-") for character in value)
    ):
        _unsafe("%s is not a safe path identifier" % name)


def resolve_work_item(delivery_root, candidate) -> Path:
    """Resolve exactly one existing direct child without following a ticket symlink."""

    root = Path(delivery_root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        _unsafe("delivery root must be an existing absolute non-symlink directory")
    root = root.resolve()
    item = Path(candidate)
    if not item.is_absolute():
        item = root / item
    if item.parent.resolve() != root or item.name in {"", ".", ".."}:
        _unsafe("work item must be one direct child of the delivery root")
    if item.is_symlink() or not item.is_dir():
        _unsafe("work item must be an existing non-symlink directory")
    return item.resolve()


def _safe_work_item_layout(value) -> Path:
    item = Path(value)
    if not item.is_absolute() or item.is_symlink() or not item.is_dir():
        _unsafe("work item must be an existing absolute non-symlink directory")
    item = item.resolve()
    for name in (".adw", ".adw/transactions", "artifacts"):
        path = item / name
        if path.is_symlink() or not path.is_dir():
            _unsafe("work-item control directories must not be symlinks")
    for name in ("state.md", "evidence.md"):
        path = item / name
        if path.is_symlink() or not path.is_file():
            _unsafe("work-item Control Block files must be regular non-symlink files")
    return item


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(str(path), flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(descriptor, view):]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_no_follow(path: Path) -> bytes:
    try:
        descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise AdwError(8, "integrity_hold", "internal control file could not be opened safely: %s" % exc)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise AdwError(8, "integrity_hold", "internal control path is not a regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise AdwError(4, "invalid_time", "lease time must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AdwError(8, "integrity_hold", "lease expiry is malformed")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise AdwError(8, "integrity_hold", "lease expiry is malformed")


def _validate_owner_metadata(metadata: Any) -> None:
    expected = {
        "work_item", "transaction_id", "request_id", "base_sequence", "base_head",
        "lead_run_ref", "host", "pid", "process_start_observation", "nonce",
        "acquired_at", "expires_at",
    }
    if not isinstance(metadata, dict) or set(metadata) != expected:
        raise AdwError(8, "integrity_hold", "lock ownership metadata fields are invalid")
    for field in ("work_item", "transaction_id", "request_id", "lead_run_ref", "host", "nonce"):
        if not isinstance(metadata[field], str) or not metadata[field]:
            raise AdwError(8, "integrity_hold", "lock ownership identity is invalid")
    for field in ("base_sequence", "pid"):
        if isinstance(metadata[field], bool) or not isinstance(metadata[field], int) or metadata[field] < 1:
            raise AdwError(8, "integrity_hold", "lock ownership numeric field is invalid")
    head = metadata["base_head"]
    if not isinstance(head, str) or not head.startswith("sha256:") or len(head) != 71:
        raise AdwError(8, "integrity_hold", "lock base audit head is invalid")
    if metadata["process_start_observation"] is not None and not isinstance(metadata["process_start_observation"], str):
        raise AdwError(8, "integrity_hold", "lock process observation is invalid")
    acquired = _parse_utc(metadata["acquired_at"])
    expires = _parse_utc(metadata["expires_at"])
    if expires <= acquired:
        raise AdwError(8, "integrity_hold", "lock lease interval is invalid")


class LeaseLock:
    """Held advisory ownership for one local write or recovery lease."""

    def __init__(self, item: Path, kind: str, descriptor: int, metadata: Dict[str, Any], metadata_bytes: bytes):
        self.item = item
        self.kind = kind
        self.path = item / ".adw" / (kind + ".lock")
        self.descriptor = descriptor
        self.metadata = metadata
        self.metadata_hash = _sha256(metadata_bytes)
        self.released = False

    @classmethod
    def acquire(
        cls, item, kind: str, work_item: str, transaction_id: str, request_id: str,
        base_sequence: int, base_head: str, lead_run_ref: str, lease_seconds: int,
        now=None,
    ) -> "LeaseLock":
        if kind not in {"write", "recovery"}:
            raise AdwError(4, "invalid_lock", "lock kind is unsupported")
        _positive_integer(lease_seconds, "lock_lease_seconds")
        current_time = now or datetime.now(timezone.utc)
        adw = Path(item) / ".adw"
        if not Path(item).is_absolute() or Path(item).is_symlink() or adw.is_symlink() or not adw.is_dir():
            _unsafe("lock path is not a contained .adw directory")
        lock_path = adw / (kind + ".lock")
        try:
            lock_path.mkdir(mode=0o700)
        except FileExistsError:
            cls._reject_existing(lock_path, current_time)
        descriptor = -1
        try:
            flock_path = lock_path / "owner.flock"
            descriptor = os.open(
                str(flock_path),
                os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            metadata = {
                "work_item": work_item,
                "transaction_id": transaction_id,
                "request_id": request_id,
                "base_sequence": base_sequence,
                "base_head": base_head,
                "lead_run_ref": lead_run_ref,
                "host": socket.gethostname(),
                "pid": os.getpid(),
                "process_start_observation": None,
                "nonce": secrets.token_hex(16),
                "acquired_at": _utc_text(current_time),
                "expires_at": _utc_text(current_time + timedelta(seconds=lease_seconds)),
            }
            metadata_bytes = canonical_json(metadata)
            _write_new(lock_path / "owner.json", metadata_bytes)
            _fsync_directory(lock_path)
            _fsync_directory(adw)
            return cls(Path(item), kind, descriptor, metadata, metadata_bytes)
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            for name in ("owner.json", "owner.flock"):
                try:
                    (lock_path / name).unlink()
                except FileNotFoundError:
                    pass
            try:
                lock_path.rmdir()
            except OSError:
                pass
            raise

    @staticmethod
    def _reject_existing(lock_path: Path, now: datetime) -> None:
        if lock_path.is_symlink() or not lock_path.is_dir():
            raise AdwError(8, "integrity_hold", "lock directory is ambiguous")
        owner_path = lock_path / "owner.json"
        flock_path = lock_path / "owner.flock"
        if owner_path.is_symlink() or flock_path.is_symlink() or not owner_path.is_file() or not flock_path.is_file():
            raise AdwError(8, "integrity_hold", "lock ownership is incomplete or ambiguous")
        before = _read_no_follow(owner_path)
        try:
            metadata = json.loads(before.decode("utf-8"), object_pairs_hook=_strict_object, parse_constant=_reject_constant)
            if not isinstance(metadata, dict) or canonical_json(metadata) != before:
                raise ValueError("non-canonical owner metadata")
            _validate_owner_metadata(metadata)
        except (AdwError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            raise AdwError(8, "integrity_hold", "lock ownership metadata is malformed")
        descriptor = os.open(str(flock_path), os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise AdwError(6, "busy", "lock is held by a live owner")
            if _read_no_follow(owner_path) != before:
                raise AdwError(8, "integrity_hold", "lock metadata changed during inspection")
            if now < _parse_utc(metadata.get("expires_at")):
                raise AdwError(6, "busy", "unheld lock lease has not expired")
            raise AdwError(8, "recovery_required", "expired orphan lock requires explicit recovery")
        finally:
            os.close(descriptor)

    @classmethod
    def claim_expired(cls, item, kind: str, recovery_events, now=None) -> "StaleLeaseClaim":
        """Preserve one expired orphan after acquiring its unchanged advisory file."""

        if kind not in {"write", "recovery"}:
            raise AdwError(4, "invalid_lock", "lock kind is unsupported")
        item = Path(item)
        if not item.is_absolute() or item.is_symlink() or not item.is_dir():
            _unsafe("stale-lock work item must be an absolute non-symlink directory")
        item = item.resolve()
        adw = item / ".adw"
        events = Path(recovery_events)
        if not events.is_absolute():
            events = item / events
        if events.is_symlink():
            _unsafe("recovery evidence directory must not be a symlink")
        events = events.resolve()
        transactions = adw / "transactions"
        try:
            relative = events.relative_to(transactions)
        except ValueError:
            _unsafe("recovery evidence must be contained under .adw/transactions")
        if len(relative.parts) != 2 or relative.parts[1] != "recovery-events":
            _unsafe("recovery evidence directory has an invalid shape")
        if any((transactions.joinpath(*relative.parts[:index])).is_symlink() for index in range(1, len(relative.parts) + 1)):
            _unsafe("recovery evidence path traverses a symlink")
        if not events.is_dir() or events.stat().st_dev != adw.stat().st_dev:
            raise AdwError(8, "integrity_hold", "recovery evidence is not on the work-item filesystem")
        lock_path = adw / (kind + ".lock")
        owner_path = lock_path / "owner.json"
        flock_path = lock_path / "owner.flock"
        if lock_path.is_symlink() or owner_path.is_symlink() or flock_path.is_symlink():
            raise AdwError(8, "integrity_hold", "stale lock path is ambiguous")
        before = _read_no_follow(owner_path)
        try:
            metadata = json.loads(before.decode("utf-8"), object_pairs_hook=_strict_object, parse_constant=_reject_constant)
            if not isinstance(metadata, dict) or canonical_json(metadata) != before:
                raise ValueError("non-canonical owner metadata")
            _validate_owner_metadata(metadata)
        except (AdwError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            raise AdwError(8, "integrity_hold", "stale lock metadata is malformed")
        current_time = now or datetime.now(timezone.utc)
        if current_time < _parse_utc(metadata.get("expires_at")):
            raise AdwError(6, "busy", "orphan lease has not expired")
        descriptor = os.open(str(flock_path), os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise AdwError(6, "busy", "stale lock is still held")
            if _read_no_follow(owner_path) != before:
                raise AdwError(8, "integrity_hold", "stale lock metadata changed during acquisition")
            target = events / ("stale-%s-%s.lock" % (kind, hashlib.sha256(before).hexdigest()[:16]))
            if target.exists() or target.is_symlink():
                raise AdwError(8, "integrity_hold", "stale lock preservation target already exists")
            os.rename(str(lock_path), str(target))
            if _read_no_follow(target / "owner.json") != before:
                raise AdwError(8, "integrity_hold", "preserved stale lock metadata changed")
            _fsync_directory(events)
            _fsync_directory(adw)
            return StaleLeaseClaim(target, descriptor, metadata, _sha256(before))
        except Exception:
            os.close(descriptor)
            raise

    def release(self) -> None:
        if self.released:
            return
        owner_path = self.path / "owner.json"
        flock_path = self.path / "owner.flock"
        try:
            if _sha256(_read_no_follow(owner_path)) != self.metadata_hash:
                raise AdwError(8, "integrity_hold", "owned lock metadata changed before release")
            if os.fstat(self.descriptor).st_ino != os.stat(str(flock_path), follow_symlinks=False).st_ino:
                raise AdwError(8, "integrity_hold", "owned advisory lock file changed before release")
            owner_path.unlink()
            flock_path.unlink()
            self.path.rmdir()
            _fsync_directory(self.item / ".adw")
        except AdwError:
            os.close(self.descriptor)
            self.released = True
            raise
        except OSError as exc:
            os.close(self.descriptor)
            self.released = True
            raise AdwError(8, "integrity_hold", "owned lock could not be released safely: %s" % exc)
        os.close(self.descriptor)
        self.released = True

    def abandon(self) -> None:
        """Simulate process death: release the OS handle but retain ownership evidence."""

        if not self.released:
            os.close(self.descriptor)
            self.released = True


class StaleLeaseClaim:
    def __init__(self, path: Path, descriptor: int, metadata: Dict[str, Any], metadata_hash: str):
        self.path = path
        self.descriptor = descriptor
        self.metadata = metadata
        self.metadata_hash = metadata_hash

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1


def verify_artifact(work_item, artifact_ref: str, integrity_ref: str, external_resolvers=None) -> str:
    """Recompute a contained local artifact or a configured immutable external one."""

    _nonempty_string(artifact_ref, "artifact_ref")
    _nonempty_string(integrity_ref, "integrity_ref")
    item = Path(work_item)
    if not item.is_absolute() or item.is_symlink() or not item.is_dir():
        _unsafe("work item must be an existing absolute non-symlink directory")
    item = item.resolve()
    if "://" in artifact_ref:
        scheme, locator = artifact_ref.split("://", 1)
        resolver = (external_resolvers or {}).get(scheme)
        if not locator or resolver is None:
            _invalid("external artifact provider is not configured and immutable")
        data = resolver(locator)
        if not isinstance(data, bytes):
            _invalid("external artifact resolver must return immutable bytes")
    else:
        relative = Path(artifact_ref)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("artifacts",):
            _unsafe("local artifact must be contained under artifacts/")
        target = item / relative
        current = item
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                _unsafe("local artifact path must not traverse a symlink")
        artifacts = (item / "artifacts").resolve()
        try:
            target.resolve(strict=True).relative_to(artifacts)
        except (FileNotFoundError, ValueError):
            _unsafe("local artifact path escapes or does not exist")
        if not target.is_file():
            _unsafe("local artifact must be a regular file")
        parent_descriptor = -1
        descriptor = -1
        try:
            parent_descriptor = _open_directory_no_follow(target.parent)
            descriptor = _open_regular_at(parent_descriptor, target.name)
            chunks = []
            while True:
                chunk = os.read(descriptor, 65536)
                if not chunk:
                    data = b"".join(chunks)
                    break
                chunks.append(chunk)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if parent_descriptor >= 0:
                os.close(parent_descriptor)
    actual = _sha256(data)
    if actual != integrity_ref:
        raise AdwError(8, "integrity_hold", "artifact integrity mismatch")
    return actual


def _exact_fields(value: Any, expected, name: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        _invalid("%s fields do not match the schema" % name)


def _nonempty_string(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        _invalid("%s must be a non-empty string" % name)


def _string_list(value: Any, name: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        _invalid("%s must be a list of non-empty strings" % name)


def _positive_integer(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _invalid("%s must be a bounded positive integer" % name)


def _validate_audit(audit: Any) -> None:
    _exact_fields(audit, AUDIT_FIELDS, "audit")
    sequence = audit["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        _invalid("audit.sequence must be a positive integer")
    head = audit["head"]
    if not isinstance(head, str) or len(head) != 71 or not head.startswith("sha256:"):
        _invalid("audit.head must be a SHA-256 integrity reference")
    try:
        int(head[7:], 16)
    except ValueError:
        _invalid("audit.head must be a SHA-256 integrity reference")
    _nonempty_string(audit["last_transaction_id"], "audit.last_transaction_id")
    _nonempty_string(audit["last_request_id"], "audit.last_request_id")


def _validate_write_policy(policy: Any) -> None:
    expected = {"policy_ref", "policy_revision", "coordination_mode", "lock_lease_seconds", "transaction_schema"}
    _exact_fields(policy, expected, "write_policy")
    _nonempty_string(policy["policy_ref"], "write_policy.policy_ref")
    _nonempty_string(policy["policy_revision"], "write_policy.policy_revision")
    if policy["coordination_mode"] != "local_single_host":
        _invalid("write_policy.coordination_mode is unsupported")
    _positive_integer(policy["lock_lease_seconds"], "write_policy.lock_lease_seconds")
    if policy["transaction_schema"] != 1:
        _invalid("write_policy.transaction_schema is unsupported")


def _validate_loop_policy(policy: Any) -> None:
    expected = {
        "policy_ref", "policy_revision", "max_attempts_per_root_cause",
        "max_review_correction_loops", "max_extension_units_per_decision",
        "max_extension_decisions_per_scope",
    }
    _exact_fields(policy, expected, "loop_policy")
    _nonempty_string(policy["policy_ref"], "loop_policy.policy_ref")
    _nonempty_string(policy["policy_revision"], "loop_policy.policy_revision")
    for field in expected - {"policy_ref", "policy_revision"}:
        _positive_integer(policy[field], "loop_policy.%s" % field)


def validate_control_pair(state: Dict[str, Any], evidence: Dict[str, Any]) -> None:
    """Validate the committed structural contract shared by both Control Blocks."""

    _exact_fields(state, STATE_FIELDS, "state")
    _exact_fields(evidence, EVIDENCE_FIELDS, "evidence")
    _nonempty_string(state["work_item"], "state.work_item")
    _nonempty_string(state["repository"], "state.repository")
    _nonempty_string(state["owner"], "state.owner")
    if evidence["work_item"] != state["work_item"]:
        _invalid("Control Blocks disagree on work_item")
    if state["state"] not in STATES:
        _invalid("state is unknown")
    if state["review_pass"] is not None:
        _invalid("review_pass is obsolete; quality gates have concrete states")
    for field in ("blocked_from_state", "resume_state"):
        if state[field] is not None and state[field] not in STATES - {"BLOCKED", "COMPLETE"}:
            _invalid("%s is invalid" % field)
    for field in ("blocked_from_review_pass", "resume_review_pass"):
        if state[field] is not None:
            _invalid("%s is obsolete; quality gates have concrete states" % field)
    blocked_fields = (
        "blocked_from_state", "blocked_from_review_pass", "resume_state", "resume_review_pass",
    )
    if state["state"] != "BLOCKED" and any(state[field] is not None for field in blocked_fields):
        _invalid("block/resume identity is allowed only in BLOCKED")
    if state["state"] == "BLOCKED" and (state["blocked_from_state"] is None or state["resume_state"] is None):
        _invalid("BLOCKED requires origin and resume states")
    for field in ("required_evidence_ids", "blocker_ids", "exception_ids"):
        _string_list(state[field], field)
    _validate_write_policy(state["write_policy"])
    _validate_loop_policy(state["loop_policy"])
    _validate_audit(state["audit"])
    _validate_audit(evidence["audit"])
    if state["audit"] != evidence["audit"]:
        _invalid("Control Blocks disagree on committed audit identity")
    _exact_fields(state["current_revisions"], REVISION_FIELDS, "current_revisions")
    for value in state["current_revisions"].values():
        if value is not None and (not isinstance(value, str) or not value):
            _invalid("revision IDs must be null or non-empty strings")
    _exact_fields(state["gate_evidence"], GATE_FIELDS, "gate_evidence")
    for value in state["gate_evidence"].values():
        if value is not None and (not isinstance(value, str) or not value):
            _invalid("gate evidence IDs must be null or non-empty strings")
    for field in ("revision_history", "transition_history"):
        if not isinstance(state[field], list):
            _invalid("%s must be an array" % field)
    for entry in state["revision_history"]:
        if not isinstance(entry, dict):
            _invalid("revision history entries must be objects")
        _exact_fields(entry, {"id", "domain", "source_ref", "fingerprint", "reason", "recorded_at", "recorder", "prior_revision"}, "revision_history entry")
        if entry["domain"] not in REVISION_FIELDS:
            _invalid("revision history domain is invalid")
    transition_fields = {
        "audit_sequence", "transaction_id", "request_id", "recorded_at", "kind", "from_state",
        "from_review_pass", "to_state", "to_review_pass", "decision_evidence_id",
        "supporting_evidence_ids", "reason", "next_action", "owner", "correction_attempt_ids",
        "correction_loop_sequence",
    }
    for entry in state["transition_history"]:
        if not isinstance(entry, dict):
            _invalid("transition history entries must be objects")
        _exact_fields(entry, transition_fields, "transition_history entry")
        if entry["kind"] not in {"advance", "correct", "block", "resume"}:
            _invalid("transition history kind is invalid")
    if not isinstance(evidence["evidence_index"], list):
        _invalid("evidence_index must be an array")
    validate_root_cause_lineage(evidence["evidence_index"])


def validate_root_cause_lineage(evidence_index) -> None:
    """Reject mechanically malformed or cyclic root-cause classification history."""

    parents = {}
    known = set()
    for entry in evidence_index:
        if not isinstance(entry, dict) or entry.get("type") != "root_cause_record":
            continue
        relation = entry.get("root_cause_relation")
        results = entry.get("root_cause_ids")
        source = entry.get("parent_root_cause_ids")
        if relation not in {"new", "refine", "reopen", "split", "merge"}:
            _invalid("root-cause relation is invalid")
        if not isinstance(results, list) or not isinstance(source, list):
            _invalid("root-cause IDs and parents must be arrays")
        _string_list(results, "root_cause_ids")
        _string_list(source, "parent_root_cause_ids")
        if len(set(results)) != len(results) or len(set(source)) != len(source):
            _invalid("root-cause IDs must be distinct")
        if relation == "new" and (len(results) != 1 or source):
            _invalid("new root cause requires one result and no parent")
        if relation in {"refine", "reopen"} and (len(results) != 1 or results[0] not in known or source):
            _invalid("refine/reopen must reuse one existing root cause without adding parents")
        if relation == "split" and (len(results) < 2 or len(source) != 1 or source[0] not in known):
            _invalid("split requires new children and one known parent")
        if relation == "merge" and (len(results) != 1 or len(source) < 2 or any(item not in known for item in source)):
            _invalid("merge requires one result and at least two known parents")
        if relation in {"new", "split", "merge"} and any(item in known for item in results):
            _invalid("new/split/merge result IDs must be new")
        if set(results) & set(source):
            _invalid("a root cause cannot be its own parent")
        for result in results:
            parents.setdefault(result, set()).update(source)
            stack = list(parents[result])
            visited = set()
            while stack:
                ancestor = stack.pop()
                if ancestor == result:
                    _invalid("root-cause lineage is cyclic")
                if ancestor not in visited:
                    visited.add(ancestor)
                    stack.extend(parents.get(ancestor, ()))
        known.update(results)


def validate_evidence_record(record, work_item, current_revisions=None, known_evidence_ids=None):
    """Validate the non-negotiable provenance fields before evidence can be recorded."""

    if not isinstance(record, dict):
        _invalid("evidence record must be an object")
    for field in ("id", "type", "producer_role", "producer_ref", "producer_proof_ref", "recorded_by", "source_ref"):
        _safe_runtime_text(record.get(field), "evidence.%s" % field)
    if record["type"] not in EVIDENCE_TYPES or record["producer_role"] not in PRODUCER_ROLES:
        _invalid("evidence type or producer role is not configured")
    if record.get("state") not in STATES or record.get("review_pass") is not None:
        _invalid("evidence state identity is invalid")
    _safe_reference(record.get("artifact_ref"), "evidence.artifact_ref")
    if not isinstance(record.get("integrity_ref"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", record["integrity_ref"]):
        _invalid("evidence artifact integrity must be a SHA-256 reference")
    if record.get("work_item") != work_item:
        _invalid("evidence record work item is invalid")
    if not isinstance(record.get("input_revisions"), dict):
        _invalid("evidence record revisions are invalid")
    if record.get("result_status") not in {"pass", "fail", "blocked", "unstable", "not_run", "not_required"}:
        _invalid("evidence record result is invalid")
    if record.get("validity_status") not in {"current", "superseded", "invalidated"}:
        _invalid("evidence record validity is invalid")
    if current_revisions is not None:
        for domain, revision in record["input_revisions"].items():
            if domain not in REVISION_FIELDS or current_revisions.get(domain) != revision:
                _invalid("evidence record revision is stale or unknown")
    for field in ("supports", "historical_supports", "supersedes"):
        values = record.get(field, [])
        _string_list(values, "evidence.%s" % field)
        if len(values) != len(set(values)) or record["id"] in values:
            _invalid("evidence support IDs must be distinct and cannot reference themselves")
        if known_evidence_ids is not None and any(value not in known_evidence_ids for value in values):
            _invalid("evidence support reference is dangling")
    gate = record.get("gate")
    if gate is not None:
        requirement = GATE_REQUIREMENTS.get(gate)
        if requirement is None:
            _invalid("evidence gate is not configured")
        evidence_type, decision, roles, state, review_pass, required_revisions = requirement
        if (
            record["type"] != evidence_type or record.get("decision") != decision
            or record["producer_role"] not in roles or record["state"] != state
            or record.get("review_pass") != review_pass or record["result_status"] != "pass"
            or record["validity_status"] != "current"
        ):
            _invalid("evidence is not eligible for the requested gate")
        for domain in required_revisions:
            revision = record["input_revisions"].get(domain)
            if not isinstance(revision, str) or not revision:
                _invalid("gate evidence omits required revision dependencies")
            if current_revisions is not None and current_revisions.get(domain) != revision:
                _invalid("gate evidence has a stale or missing required revision dependency")
    elif record["type"] == "gate_decision":
        roles = ROUTE_DECISION_ROLES.get(record.get("decision"))
        if roles is None or record["producer_role"] not in roles or record["result_status"] != "pass" or record["validity_status"] != "current":
            _invalid("route decision is not authorized")


@dataclass(frozen=True)
class ControlBlock:
    value: Dict[str, Any]
    narrative: bytes

    @classmethod
    def parse(cls, raw: bytes) -> "ControlBlock":
        prefix = b"---\n"
        separator = b"\n---\n"
        if not raw.startswith(prefix):
            raise AdwError(4, "invalid_control_block", "missing opening Control Block delimiter")
        end = raw.find(separator, len(prefix))
        if end < 0:
            raise AdwError(4, "invalid_control_block", "missing closing Control Block delimiter")
        encoded = raw[len(prefix):end]
        try:
            value = json.loads(
                encoded.decode("utf-8"),
                object_pairs_hook=_strict_object,
                parse_constant=_reject_constant,
            )
            _reject_floats(value)
            value = _normalize_json(value)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            raise AdwError(4, "invalid_control_block", "invalid strict JSON: %s" % exc)
        if not isinstance(value, dict):
            raise AdwError(4, "invalid_control_block", "Control Block root must be an object")
        return cls(value=value, narrative=raw[end + len(separator):])

    def replace(self, value: Dict[str, Any]) -> bytes:
        try:
            normalized = _normalize_json(value)
            if not isinstance(normalized, dict):
                _invalid("Control Block root must be an object")
            encoded = json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        except AdwError:
            raise
        except (TypeError, ValueError, UnicodeEncodeError) as exc:
            raise AdwError(4, "invalid_control_block", "invalid Control Block value: %s" % exc)
        return b"---\n" + encoded + b"\n---\n" + self.narrative


@dataclass(frozen=True)
class PreparedTransaction:
    base: Dict[str, bytes]
    staged: Dict[str, bytes]
    artifacts: Dict[str, bytes]
    audit_event: Dict[str, Any]
    commit_marker: Dict[str, Any]
    manifest: Dict[str, Any]


def _control_projection(value: Dict[str, Any]) -> Dict[str, Any]:
    projected = _normalize_json(value)
    projected["audit"] = dict(projected["audit"])
    projected["audit"].pop("head", None)
    return projected


def _artifact_payloads(artifacts) -> Dict[str, bytes]:
    if artifacts is None:
        return {}
    if not isinstance(artifacts, dict):
        _invalid("transaction artifacts must be an object mapping paths to bytes")
    normalized = {}
    for name, data in artifacts.items():
        if not isinstance(name, str):
            _invalid("transaction artifact paths must be strings")
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("artifacts",):
            _unsafe("transaction artifact path must be contained under artifacts/")
        if not isinstance(data, bytes):
            _invalid("transaction artifacts must be immutable bytes")
        normalized_name = path.as_posix()
        if normalized_name in normalized:
            _invalid("transaction artifact paths must be distinct after normalization")
        normalized[normalized_name] = data
    return dict(sorted(normalized.items()))


def _contained_artifact_target(item: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2 or relative.parts[0] != "artifacts":
        _unsafe("artifact target must be a file contained under artifacts/")
    current = item
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink() or not current.is_dir():
            _unsafe("artifact target parent is missing or traverses a symlink")
    target = current / relative.name
    if target.is_symlink():
        _unsafe("artifact target must not be a symlink")
    return target


def build_transaction(
    state_bytes: bytes,
    evidence_bytes: bytes,
    proposed_state: Dict[str, Any],
    proposed_evidence: Dict[str, Any],
    *,
    transaction_id: str,
    request_id: str,
    command: str,
    safe_arguments: Dict[str, Any],
    lead_run_ref: str,
    semantic_ids,
    intended_result: Dict[str, Any],
    started_at: datetime,
    prepared_at: datetime,
    artifacts=None,
) -> PreparedTransaction:
    """Build every transaction-owned representation from mappings and semantic inputs."""

    for value, name in (
        (transaction_id, "transaction_id"), (request_id, "request_id"),
        (command, "command"), (lead_run_ref, "lead_run_ref"),
    ):
        _nonempty_string(value, name)
    if not isinstance(safe_arguments, dict) or not isinstance(intended_result, dict):
        _invalid("safe_arguments and intended_result must be JSON objects")
    if not isinstance(semantic_ids, list):
        _invalid("semantic_ids must be an array")
    state_document = ControlBlock.parse(state_bytes)
    evidence_document = ControlBlock.parse(evidence_bytes)
    validate_control_pair(state_document.value, evidence_document.value)
    proposed_state = _normalize_json(proposed_state)
    proposed_evidence = _normalize_json(proposed_evidence)
    validate_control_pair(proposed_state, proposed_evidence)
    base_state = state_document.value
    base_evidence = evidence_document.value
    if proposed_state["work_item"] != base_state["work_item"]:
        _invalid("transaction cannot change work_item")
    if proposed_state["audit"] != base_state["audit"] or proposed_evidence["audit"] != base_evidence["audit"]:
        _invalid("caller cannot select a new audit identity")
    if proposed_state["write_policy"] != base_state["write_policy"]:
        _invalid("write policy is immutable after initialization")
    if proposed_state["loop_policy"] != base_state["loop_policy"]:
        _invalid("loop policy cannot be caller-edited")
    ids = sorted(set(semantic_ids))
    if len(ids) != len(semantic_ids) or any(not isinstance(item, str) or not item for item in ids):
        _invalid("semantic IDs must be distinct non-empty strings")
    artifact_payloads = _artifact_payloads(artifacts)
    argument_hash = _sha256(canonical_json({"command": command, "safe_arguments": safe_arguments}))
    sequence = base_state["audit"]["sequence"] + 1
    new_audit = {
        "sequence": sequence,
        "head": None,
        "last_transaction_id": transaction_id,
        "last_request_id": request_id,
    }
    proposed_state["audit"] = dict(new_audit)
    proposed_evidence["audit"] = dict(new_audit)
    before = {"state.md": state_bytes, "evidence.md": evidence_bytes}
    before_documents = {"state.md": state_document, "evidence.md": evidence_document}
    after_mappings = {"state.md": proposed_state, "evidence.md": proposed_evidence}
    control_hashes = {}
    narrative_hashes = {}
    for name, mapping in after_mappings.items():
        control_hashes[name] = {
            "before": _sha256(canonical_json(before_documents[name].value)),
            "after": _sha256(canonical_json(_control_projection(mapping))),
        }
        narrative_hashes[name] = {
            "before": _sha256(before_documents[name].narrative),
            "after": _sha256(before_documents[name].narrative),
        }
    event = {
        "schema": 1,
        "work_item": base_state["work_item"],
        "sequence": sequence,
        "transaction_id": transaction_id,
        "request_id": request_id,
        "command": command,
        "safe_argument_hash": argument_hash,
        "recorded_by": lead_run_ref,
        "started_at": _utc_text(started_at),
        "prepared_at": _utc_text(prepared_at),
        "previous_sequence": base_state["audit"]["sequence"],
        "previous_head": base_state["audit"]["head"],
        "affected_control_blocks": sorted(after_mappings),
        "semantic_ids": ids,
        "artifacts": [
            {"path": name, "integrity_ref": _sha256(data)}
            for name, data in artifact_payloads.items()
        ],
        "control_block_hashes": control_hashes,
        "narrative_hashes": narrative_hashes,
        "intended_result": _normalize_json(intended_result),
    }
    head = _sha256(canonical_json(event))
    proposed_state["audit"]["head"] = head
    proposed_evidence["audit"]["head"] = head
    validate_control_pair(proposed_state, proposed_evidence)
    staged = {
        "state.md": state_document.replace(proposed_state),
        "evidence.md": evidence_document.replace(proposed_evidence),
    }
    target_hashes = {name: _sha256(data) for name, data in staged.items()}
    artifact_hashes = {name: _sha256(data) for name, data in artifact_payloads.items()}
    marker = {
        "schema": 1,
        "work_item": base_state["work_item"],
        "sequence": sequence,
        "transaction_id": transaction_id,
        "request_id": request_id,
        "event_hash": head,
        "result_hash": _sha256(canonical_json(event["intended_result"])),
        "target_hashes": target_hashes,
        "artifact_hashes": artifact_hashes,
        "outcome": "committed",
        "commit_recorded_at": _utc_text(prepared_at),
    }
    manifest = {
        "schema": 1,
        "work_item": base_state["work_item"],
        "sequence": sequence,
        "transaction_id": transaction_id,
        "request_id": request_id,
        "command_input_hash": argument_hash,
        "event_hash": head,
        "expected_commit_marker_hash": _sha256(canonical_json(marker)),
        "targets": {
            name: {"before_hash": _sha256(before[name]), "staged_hash": target_hashes[name]}
            for name in sorted(staged)
        },
        "artifacts": artifact_hashes,
    }
    return PreparedTransaction(before, staged, artifact_payloads, event, marker, manifest)


def ensure_local_filesystem(item: Path) -> None:
    """Fail closed unless the configured work item is on one observed local mount."""

    try:
        output = subprocess.run(
            ["/sbin/mount"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        raise AdwError(8, "integrity_hold", "local filesystem capability could not be established")
    resolved = str(item.resolve())
    matches = []
    for line in output.splitlines():
        if " on " not in line or " (" not in line or not line.endswith(")"):
            continue
        mount_point = line.split(" on ", 1)[1].rsplit(" (", 1)[0]
        options = {value.strip() for value in line.rsplit(" (", 1)[1][:-1].split(",")}
        try:
            contained = os.path.commonpath([resolved, mount_point]) == mount_point
        except ValueError:
            contained = False
        if contained:
            matches.append((len(mount_point), options))
    if not matches or "local" not in max(matches, key=lambda value: value[0])[1]:
        raise AdwError(8, "integrity_hold", "work item is not on a supported local filesystem")
    devices = {(item / name).stat().st_dev for name in (".", ".adw", ".adw/transactions", "artifacts")}
    if len(devices) != 1:
        raise AdwError(8, "integrity_hold", "work item journal crosses filesystem devices")


def _open_directory_no_follow(path: Path) -> int:
    """Open every component of one absolute directory without following symlinks."""

    path = Path(path)
    if not path.is_absolute():
        _unsafe("internal publication directory must be absolute")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise AdwError(8, "integrity_hold", "publication directory changed or is unsafe: %s" % exc)


def _open_regular_at(directory: int, name: str) -> int:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            dir_fd=directory,
        )
    except OSError as exc:
        raise AdwError(8, "integrity_hold", "publication source or target is unsafe: %s" % exc)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise AdwError(8, "integrity_hold", "publication source or target is not a regular file")
    return descriptor


def _publish_no_clobber(source: Path, target: Path, on_publish=None) -> None:
    source_parent = -1
    target_parent = -1
    source_descriptor = -1
    target_descriptor = -1
    try:
        source_parent = _open_directory_no_follow(source.parent)
        target_parent = _open_directory_no_follow(target.parent)
        source_descriptor = _open_regular_at(source_parent, source.name)
        try:
            os.link(
                source.name, target.name,
                src_dir_fd=source_parent, dst_dir_fd=target_parent, follow_symlinks=False,
            )
        except FileExistsError:
            raise AdwError(8, "integrity_hold", "immutable publication target already exists")
        if on_publish:
            on_publish()
        target_descriptor = _open_regular_at(target_parent, target.name)
        source_identity = os.fstat(source_descriptor)
        target_identity = os.fstat(target_descriptor)
        if (source_identity.st_dev, source_identity.st_ino) != (target_identity.st_dev, target_identity.st_ino):
            raise AdwError(8, "integrity_hold", "immutable publication identity changed")
        os.fsync(target_parent)
    except OSError as exc:
        raise AdwError(8, "integrity_hold", "immutable publication failed safely: %s" % exc)
    finally:
        if target_descriptor >= 0:
            os.close(target_descriptor)
        if source_descriptor >= 0:
            os.close(source_descriptor)
        if source_parent >= 0:
            os.close(source_parent)
        if target_parent >= 0:
            os.close(target_parent)


def _replace_from_journal(source: Path, target: Path, transaction_id: str) -> None:
    temporary_name = ".%s.%s.tmp" % (target.name, transaction_id)
    source_parent = -1
    target_parent = -1
    source_descriptor = -1
    temporary_descriptor = -1
    try:
        source_parent = _open_directory_no_follow(source.parent)
        target_parent = _open_directory_no_follow(target.parent)
        source_descriptor = _open_regular_at(source_parent, source.name)
        try:
            os.link(
                source.name, temporary_name,
                src_dir_fd=source_parent, dst_dir_fd=target_parent, follow_symlinks=False,
            )
        except FileExistsError:
            raise AdwError(8, "integrity_hold", "mutable replacement temporary path already exists")
        temporary_descriptor = _open_regular_at(target_parent, temporary_name)
        source_identity = os.fstat(source_descriptor)
        temporary_identity = os.fstat(temporary_descriptor)
        if (source_identity.st_dev, source_identity.st_ino) != (temporary_identity.st_dev, temporary_identity.st_ino):
            raise AdwError(8, "integrity_hold", "mutable replacement identity changed")
        os.fsync(target_parent)
        os.replace(temporary_name, target.name, src_dir_fd=target_parent, dst_dir_fd=target_parent)
        os.fsync(target_parent)
    except OSError as exc:
        raise AdwError(8, "integrity_hold", "mutable replacement failed safely: %s" % exc)
    finally:
        if temporary_descriptor >= 0:
            os.close(temporary_descriptor)
        if source_descriptor >= 0:
            os.close(source_descriptor)
        if source_parent >= 0:
            os.close(source_parent)
        if target_parent >= 0:
            os.close(target_parent)


def _stage_transaction(item: Path, prepared: PreparedTransaction) -> Path:
    sequence = prepared.audit_event["sequence"]
    transaction_id = prepared.audit_event["transaction_id"]
    transaction = item / ".adw" / "transactions" / ("%s-%s" % (sequence, transaction_id))
    try:
        transaction.mkdir(mode=0o700)
    except FileExistsError:
        raise AdwError(8, "integrity_hold", "transaction journal identity already exists")
    for directory in ("before", "staged", "staged/artifacts", "recovery-events"):
        (transaction / directory).mkdir(mode=0o700)
    for name, data in prepared.base.items():
        _write_new(transaction / "before" / name, data)
    for name, data in prepared.staged.items():
        _write_new(transaction / "staged" / name, data)
    for name, data in prepared.artifacts.items():
        relative = Path(name).relative_to("artifacts")
        target = transaction / "staged" / "artifacts" / relative
        if not target.parent.is_dir():
            target.parent.mkdir(mode=0o700, parents=True)
        _write_new(target, data)
    _write_new(transaction / "audit-event.json", canonical_json(prepared.audit_event))
    _write_new(transaction / "staged" / "commit-marker.json", canonical_json(prepared.commit_marker))
    _write_new(transaction / "manifest.json", canonical_json(prepared.manifest))
    for directory in (transaction / "before", transaction / "staged", transaction):
        _fsync_directory(directory)
    _fsync_directory(transaction.parent)
    return transaction


def _record_abort(transaction: Path, prepared: PreparedTransaction, error: Exception, now: datetime) -> None:
    abort = {
        "schema": 1,
        "work_item": prepared.audit_event["work_item"],
        "transaction_id": prepared.audit_event["transaction_id"],
        "request_id": prepared.audit_event["request_id"],
        "event_hash": _sha256(canonical_json(prepared.audit_event)),
        "outcome": "aborted",
        "aborted_at": _utc_text(now),
        "reason_kind": getattr(error, "kind", "unexpected_error"),
    }
    abort_bytes = canonical_json(abort)
    _write_new(transaction / "abort.json", abort_bytes)
    recovery_event = {
        "schema": 1,
        "work_item": prepared.audit_event["work_item"],
        "transaction_id": prepared.audit_event["transaction_id"],
        "request_id": prepared.audit_event["request_id"],
        "action": "transaction_aborted",
        "event_hash": abort["event_hash"],
        "abort_hash": _sha256(abort_bytes),
        "recorded_at": _utc_text(now),
    }
    name = "abort-%s.json" % hashlib.sha256(prepared.audit_event["request_id"].encode("utf-8")).hexdigest()[:16]
    _write_new(transaction / "recovery-events" / name, canonical_json(recovery_event))
    _fsync_directory(transaction / "recovery-events")
    _fsync_directory(transaction)


def _rollback_transaction(
    item: Path,
    transaction: Path,
    prepared: PreparedTransaction,
    replaced,
    published_artifacts,
    error: Exception,
    now: datetime,
) -> None:
    transaction_id = prepared.audit_event["transaction_id"]
    for name in reversed(replaced):
        target = item / name
        current_hash = _sha256(_read_no_follow(target))
        before_hash = prepared.manifest["targets"][name]["before_hash"]
        staged_hash = prepared.manifest["targets"][name]["staged_hash"]
        if current_hash == staged_hash:
            _replace_from_journal(transaction / "before" / name, target, transaction_id + "-rollback")
        elif current_hash != before_hash:
            raise AdwError(8, "integrity_hold", "mutable target has an unexpected third hash")
    if published_artifacts:
        orphaned = transaction / "orphaned-artifacts"
        orphaned.mkdir(mode=0o700)
        for name in published_artifacts:
            target = item / name
            if _sha256(_read_no_follow(target)) != prepared.manifest["artifacts"][name]:
                raise AdwError(8, "integrity_hold", "published artifact has an unexpected third hash")
            orphan = orphaned / hashlib.sha256(name.encode("utf-8")).hexdigest()
            if orphan.exists():
                raise AdwError(8, "integrity_hold", "artifact orphan target already exists")
            os.rename(str(target), str(orphan))
        _fsync_directory(orphaned)
        _fsync_directory(item / "artifacts")
    _record_abort(transaction, prepared, error, now)


def _read_canonical_object(path: Path) -> Dict[str, Any]:
    data = _read_no_follow(path)
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_strict_object, parse_constant=_reject_constant)
        if not isinstance(value, dict) or canonical_json(value) != data:
            raise ValueError("non-canonical object")
        return value
    except (AdwError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise AdwError(8, "integrity_hold", "journal object is malformed: %s" % path.name)


def _validate_aborted_transaction(transaction: Path, manifest: Dict[str, Any]) -> None:
    abort_path = transaction / "abort.json"
    abort_bytes = _read_no_follow(abort_path)
    abort = _read_canonical_object(abort_path)
    event_bytes = _read_no_follow(transaction / "audit-event.json")
    event = _read_canonical_object(transaction / "audit-event.json")
    identity = (
        manifest.get("work_item"), manifest.get("transaction_id"), manifest.get("request_id"),
    )
    if manifest.get("schema") != 1 or event.get("schema") != 1 or abort.get("schema") != 1:
        raise AdwError(8, "integrity_hold", "aborted transaction schema is unsupported")
    if identity != (
        event.get("work_item"), event.get("transaction_id"), event.get("request_id"),
    ) or identity != (
        abort.get("work_item"), abort.get("transaction_id"), abort.get("request_id"),
    ):
        raise AdwError(8, "integrity_hold", "aborted transaction identities disagree")
    event_hash = _sha256(event_bytes)
    if event_hash != manifest.get("event_hash") or abort.get("event_hash") != event_hash:
        raise AdwError(8, "integrity_hold", "aborted event hash is inconsistent")
    if abort.get("outcome") != "aborted" or not isinstance(abort.get("reason_kind"), str):
        raise AdwError(8, "integrity_hold", "abort marker semantics are invalid")
    _parse_utc(abort.get("aborted_at"))
    events_path = transaction / "recovery-events"
    if events_path.is_symlink() or not events_path.is_dir():
        raise AdwError(8, "integrity_hold", "abort recovery evidence directory is invalid")
    matching = 0
    abort_hash = _sha256(abort_bytes)
    for path in events_path.iterdir():
        if path.is_symlink():
            raise AdwError(8, "integrity_hold", "abort recovery evidence contains a symlink")
        if path.is_dir():
            continue
        recovery = _read_canonical_object(path)
        if recovery.get("action") != "transaction_aborted":
            continue
        if (
            recovery.get("schema") != 1
            or identity != (
                recovery.get("work_item"), recovery.get("transaction_id"), recovery.get("request_id"),
            )
            or recovery.get("event_hash") != event_hash
            or recovery.get("abort_hash") != abort_hash
        ):
            raise AdwError(8, "integrity_hold", "abort recovery evidence is inconsistent")
        _parse_utc(recovery.get("recorded_at"))
        matching += 1
    if matching != 1:
        raise AdwError(8, "integrity_hold", "abort marker requires exactly one matching recovery event")


def _idempotency_result(transactions: Path, request_id: str, input_hash: str):
    matches = []
    for transaction in sorted(transactions.iterdir()):
        if transaction.is_symlink() or not transaction.is_dir():
            raise AdwError(8, "integrity_hold", "transaction journal contains an unsafe entry")
        manifest_path = transaction / "manifest.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise AdwError(8, "recovery_required", "transaction journal is incomplete")
        manifest = _read_canonical_object(manifest_path)
        if manifest.get("request_id") == request_id:
            matches.append((transaction, manifest))
    if not matches:
        return None
    if len(matches) != 1:
        raise AdwError(8, "integrity_hold", "request ID appears in multiple transaction journals")
    transaction, manifest = matches[0]
    if manifest.get("command_input_hash") != input_hash:
        raise AdwError(7, "idempotency_conflict", "request ID was already used for different input")
    commit_path = transaction / "commit.json"
    abort_path = transaction / "abort.json"
    if commit_path.exists() and abort_path.exists():
        raise AdwError(8, "integrity_hold", "transaction has conflicting terminal markers")
    if commit_path.is_file():
        marker_bytes = _read_no_follow(commit_path)
        if _sha256(marker_bytes) != manifest.get("expected_commit_marker_hash"):
            raise AdwError(8, "integrity_hold", "committed marker does not match its manifest")
        marker = _read_canonical_object(commit_path)
        event = _read_canonical_object(transaction / "audit-event.json")
        if _sha256(canonical_json(event)) != manifest.get("event_hash") or marker.get("event_hash") != manifest.get("event_hash"):
            raise AdwError(8, "integrity_hold", "committed event identity is inconsistent")
        audit = {
            "sequence": marker["sequence"],
            "head": marker["event_hash"],
            "last_transaction_id": marker["transaction_id"],
            "last_request_id": marker["request_id"],
        }
        return {"status": "committed", "audit": audit, "result": event["intended_result"]}
    if abort_path.is_file():
        abort = _read_canonical_object(abort_path)
        return {
            "status": "aborted",
            "transaction_id": abort["transaction_id"],
            "request_id": abort["request_id"],
        }
    raise AdwError(8, "recovery_required", "request has a prepared transaction")


def commit_transaction(
    item,
    proposed_state,
    proposed_evidence,
    *,
    expected_sequence: int,
    expected_head: str,
    transaction_id: str,
    request_id: str,
    command: str,
    safe_arguments: Dict[str, Any],
    lead_run_ref: str,
    semantic_ids,
    intended_result: Dict[str, Any],
    now=None,
    artifacts=None,
    step_hook=None,
    crash_at=None,
    clock=None,
) -> Dict[str, Any]:
    """Journal and publish one already-authorized semantic mutation."""

    _path_identifier(transaction_id, "transaction_id")
    item = _safe_work_item_layout(item)
    ensure_local_filesystem(item)
    state_bytes = _read_no_follow(item / "state.md")
    evidence_bytes = _read_no_follow(item / "evidence.md")
    current_state = ControlBlock.parse(state_bytes).value
    current_evidence = ControlBlock.parse(evidence_bytes).value
    validate_control_pair(current_state, current_evidence)
    if now is not None and clock is not None:
        _invalid("use either now or clock, not both")
    time_source = clock or ((lambda: now) if now is not None else (lambda: datetime.now(timezone.utc)))
    current_time = time_source()
    failure_time = current_time
    input_hash = _sha256(canonical_json({"command": command, "safe_arguments": safe_arguments}))
    lock = LeaseLock.acquire(
        item, "write", current_state["work_item"], transaction_id, request_id,
        expected_sequence, expected_head, lead_run_ref,
        current_state["write_policy"]["lock_lease_seconds"], now=current_time,
    )
    transaction = None
    prepared = None
    replaced = []
    published_artifacts = []
    abandoned = False
    try:
        state_bytes = _read_no_follow(item / "state.md")
        evidence_bytes = _read_no_follow(item / "evidence.md")
        current_state = ControlBlock.parse(state_bytes).value
        current_evidence = ControlBlock.parse(evidence_bytes).value
        validate_control_pair(current_state, current_evidence)
        prior_result = _idempotency_result(item / ".adw" / "transactions", request_id, input_hash)
        if prior_result is not None:
            _validate_committed_journal(item, current_state, current_evidence)
            return prior_result
        _validate_committed_journal(item, current_state, current_evidence)
        if current_state["audit"]["sequence"] != expected_sequence or current_state["audit"]["head"] != expected_head:
            raise AdwError(5, "stale_snapshot", "expected audit identity is stale")
        prepared = build_transaction(
            state_bytes, evidence_bytes, proposed_state, proposed_evidence,
            transaction_id=transaction_id, request_id=request_id, command=command,
            safe_arguments=safe_arguments, lead_run_ref=lead_run_ref,
            semantic_ids=semantic_ids, intended_result=intended_result,
            started_at=current_time, prepared_at=current_time, artifacts=artifacts,
        )
        for artifact_name in prepared.artifacts:
            _contained_artifact_target(item, artifact_name)
        transaction = _stage_transaction(item, prepared)
        if crash_at == "after_preparation":
            raise InjectedCrash(crash_at)
        if step_hook:
            step_hook("prepared", None, item)
        publication_time = time_source()
        failure_time = publication_time
        if publication_time >= _parse_utc(lock.metadata["expires_at"]):
            raise AdwError(6, "busy", "lease expired before publication")
        for name in sorted(prepared.artifacts):
            relative = Path(name).relative_to("artifacts")
            target = _contained_artifact_target(item, name)
            if step_hook:
                step_hook("before_artifact_publish", name, item)
            _publish_no_clobber(
                transaction / "staged" / "artifacts" / relative,
                target,
                on_publish=lambda name=name: published_artifacts.append(name),
            )
            if crash_at == "after_artifact:" + name:
                raise InjectedCrash(crash_at)
        for name in ("state.md", "evidence.md"):
            target = item / name
            if step_hook:
                step_hook("before_replace", name, item)
            if _sha256(_read_no_follow(target)) != prepared.manifest["targets"][name]["before_hash"]:
                raise AdwError(5, "state_conflict", "%s changed before replacement" % name)
            _replace_from_journal(transaction / "staged" / name, target, transaction_id)
            replaced.append(name)
            if crash_at == "after_replace:" + name:
                raise InjectedCrash(crash_at)
            if step_hook:
                step_hook("after_replace", name, item)
        for name, expected in prepared.manifest["targets"].items():
            if _sha256(_read_no_follow(item / name)) != expected["staged_hash"]:
                raise AdwError(8, "integrity_hold", "published mutable target hash mismatch")
        for name, expected in prepared.manifest["artifacts"].items():
            if _sha256(_read_no_follow(item / name)) != expected:
                raise AdwError(8, "integrity_hold", "published artifact hash mismatch")
        if crash_at == "after_verification":
            raise InjectedCrash(crash_at)
        _publish_no_clobber(transaction / "staged" / "commit-marker.json", transaction / "commit.json")
        if crash_at == "after_commit_marker":
            raise InjectedCrash(crash_at)
        return {"status": "committed", "audit": ControlBlock.parse(prepared.staged["state.md"]).value["audit"], "result": intended_result}
    except InjectedCrash:
        lock.abandon()
        abandoned = True
        raise
    except Exception as error:
        if transaction is not None and prepared is not None and not (transaction / "commit.json").exists():
            _rollback_transaction(
                item, transaction, prepared, replaced, published_artifacts, error, failure_time,
            )
        raise
    finally:
        if not abandoned:
            lock.release()


@dataclass(frozen=True)
class CommittedSnapshot:
    state: Dict[str, Any]
    evidence: Dict[str, Any]
    audit: Dict[str, Any]
    token: str


def _snapshot_fingerprint(item: Path):
    roots = [
        item / "state.md", item / "evidence.md", item / ".adw" / "runtime-configuration.json",
        item / ".adw" / "transactions", item / "artifacts",
    ]
    values = []
    for root in roots:
        if root.is_symlink():
            raise AdwError(8, "integrity_hold", "snapshot path traverses a symlink")
        if root.is_file():
            values.append((root.relative_to(item).as_posix(), _sha256(_read_no_follow(root))))
            continue
        if not root.is_dir():
            raise AdwError(8, "integrity_hold", "required snapshot path is missing")
        for directory, names, files in os.walk(str(root), followlinks=False):
            directory_path = Path(directory)
            for name in names:
                if (directory_path / name).is_symlink():
                    raise AdwError(8, "integrity_hold", "snapshot directory contains a symlink")
            for name in files:
                path = directory_path / name
                if path.is_symlink():
                    raise AdwError(8, "integrity_hold", "snapshot file is a symlink")
                values.append((path.relative_to(item).as_posix(), _sha256(_read_no_follow(path))))
    for name in ("write.lock", "recovery.lock"):
        path = item / ".adw" / name
        values.append((".adw/" + name, "present" if path.exists() else "absent"))
    return tuple(sorted(values))


def _reject_active_locks(item: Path, now: datetime) -> None:
    for kind in ("write", "recovery"):
        path = item / ".adw" / (kind + ".lock")
        if path.exists() or path.is_symlink():
            LeaseLock._reject_existing(path, now)


def _validate_committed_journal(item: Path, current_state: Dict[str, Any], current_evidence: Dict[str, Any]) -> None:
    committed = {}
    transactions = item / ".adw" / "transactions"
    for transaction in sorted(transactions.iterdir()):
        if transaction.is_symlink() or not transaction.is_dir():
            raise AdwError(8, "integrity_hold", "transaction journal contains an unsafe entry")
        manifest = _read_canonical_object(transaction / "manifest.json")
        commit_path = transaction / "commit.json"
        abort_path = transaction / "abort.json"
        if commit_path.exists() and abort_path.exists():
            raise AdwError(8, "integrity_hold", "transaction has conflicting terminal markers")
        if abort_path.is_file():
            _validate_aborted_transaction(transaction, manifest)
            continue
        if not commit_path.is_file():
            raise AdwError(8, "recovery_required", "prepared transaction has no terminal marker")
        marker_bytes = _read_no_follow(commit_path)
        marker = _read_canonical_object(commit_path)
        event_bytes = _read_no_follow(transaction / "audit-event.json")
        event = _read_canonical_object(transaction / "audit-event.json")
        event_hash = _sha256(event_bytes)
        if manifest.get("schema") != 1 or marker.get("schema") != 1 or event.get("schema") != 1:
            raise AdwError(8, "integrity_hold", "transaction schema is unsupported")
        if marker.get("outcome") != "committed":
            raise AdwError(8, "integrity_hold", "commit marker outcome is invalid")
        if marker.get("commit_recorded_at") != event.get("prepared_at"):
            raise AdwError(8, "integrity_hold", "commit marker record time is inconsistent")
        if marker.get("result_hash") != _sha256(canonical_json(event.get("intended_result"))):
            raise AdwError(8, "integrity_hold", "commit marker result hash is invalid")
        if event.get("affected_control_blocks") != ["evidence.md", "state.md"]:
            raise AdwError(8, "integrity_hold", "audit event affected-Control-Block set is invalid")
        if _sha256(marker_bytes) != manifest.get("expected_commit_marker_hash"):
            raise AdwError(8, "integrity_hold", "commit marker hash does not match manifest")
        if _read_no_follow(transaction / "staged" / "commit-marker.json") != marker_bytes:
            raise AdwError(8, "integrity_hold", "published commit marker differs from its staged candidate")
        if event_hash != manifest.get("event_hash") or marker.get("event_hash") != event_hash:
            raise AdwError(8, "integrity_hold", "audit event hash does not match transaction metadata")
        sequence = event.get("sequence")
        identity = (event.get("work_item"), sequence, event.get("transaction_id"), event.get("request_id"))
        if identity != (
            manifest.get("work_item"), manifest.get("sequence"), manifest.get("transaction_id"), manifest.get("request_id"),
        ) or identity != (
            marker.get("work_item"), marker.get("sequence"), marker.get("transaction_id"), marker.get("request_id"),
        ):
            raise AdwError(8, "integrity_hold", "transaction identities disagree")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1 or sequence in committed:
            raise AdwError(8, "integrity_hold", "audit sequence is invalid or duplicated")
        if sequence == 1:
            runtime_configuration = item / ".adw" / "runtime-configuration.json"
            expected_configuration = event.get("intended_result", {}).get("runtime_configuration_sha256")
            if runtime_configuration.is_symlink() or not runtime_configuration.is_file() or _sha256(_read_no_follow(runtime_configuration)) != expected_configuration:
                raise AdwError(8, "integrity_hold", "ticket runtime configuration does not match genesis")
        if transaction.name != "%s-%s" % (sequence, event.get("transaction_id")):
            raise AdwError(8, "integrity_hold", "transaction directory identity is inconsistent")
        for name in ("state.md", "evidence.md"):
            target = manifest.get("targets", {}).get(name)
            if not isinstance(target, dict):
                raise AdwError(8, "integrity_hold", "manifest target is missing")
            staged_path = transaction / "staged" / name
            staged_bytes = _read_no_follow(staged_path)
            if _sha256(staged_bytes) != target.get("staged_hash") or marker.get("target_hashes", {}).get(name) != target.get("staged_hash"):
                raise AdwError(8, "integrity_hold", "staged target hash is inconsistent")
            staged_document = ControlBlock.parse(staged_bytes)
            expected_audit = {
                "sequence": sequence,
                "head": event_hash,
                "last_transaction_id": event["transaction_id"],
                "last_request_id": event["request_id"],
            }
            if staged_document.value.get("audit") != expected_audit:
                raise AdwError(8, "integrity_hold", "staged Control Block audit identity is inconsistent")
            hashes = event.get("control_block_hashes", {}).get(name, {})
            if _sha256(canonical_json(_control_projection(staged_document.value))) != hashes.get("after"):
                raise AdwError(8, "integrity_hold", "after-Control-Block hash is inconsistent")
            narratives = event.get("narrative_hashes", {}).get(name, {})
            if _sha256(staged_document.narrative) != narratives.get("after"):
                raise AdwError(8, "integrity_hold", "after-narrative hash is inconsistent")
            if sequence == 1:
                if target.get("before_hash") is not None or hashes.get("before") is not None or narratives.get("before") is not None:
                    raise AdwError(8, "integrity_hold", "genesis before-image must be null")
            else:
                before_bytes = _read_no_follow(transaction / "before" / name)
                before_document = ControlBlock.parse(before_bytes)
                if _sha256(before_bytes) != target.get("before_hash"):
                    raise AdwError(8, "integrity_hold", "before-file hash is inconsistent")
                if _sha256(canonical_json(before_document.value)) != hashes.get("before"):
                    raise AdwError(8, "integrity_hold", "before-Control-Block hash is inconsistent")
                if _sha256(before_document.narrative) != narratives.get("before"):
                    raise AdwError(8, "integrity_hold", "before-narrative hash is inconsistent")
        artifact_hashes = manifest.get("artifacts", {})
        if artifact_hashes != marker.get("artifact_hashes"):
            raise AdwError(8, "integrity_hold", "artifact hashes disagree")
        event_artifacts = {
            value.get("path"): value.get("integrity_ref")
            for value in event.get("artifacts", [])
            if isinstance(value, dict)
        }
        if len(event_artifacts) != len(event.get("artifacts", [])) or event_artifacts != artifact_hashes:
            raise AdwError(8, "integrity_hold", "audit event does not bind the artifact manifest")
        for name, expected in artifact_hashes.items():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("artifacts",):
                raise AdwError(8, "integrity_hold", "journal artifact path is unsafe")
            relative = path.relative_to("artifacts")
            if _sha256(_read_no_follow(transaction / "staged" / "artifacts" / relative)) != expected:
                raise AdwError(8, "integrity_hold", "staged artifact hash is inconsistent")
            if _sha256(_read_no_follow(item / name)) != expected:
                raise AdwError(8, "integrity_hold", "published artifact hash is inconsistent")
        committed[sequence] = (transaction, manifest, marker, event, event_hash)
    final_sequence = current_state["audit"]["sequence"]
    if set(committed) != set(range(1, final_sequence + 1)):
        raise AdwError(8, "integrity_hold", "committed audit chain has a gap or extra sequence")
    previous_head = None
    previous_manifest = None
    base_policies = None
    for sequence in range(1, final_sequence + 1):
        transaction, manifest, marker, event, event_hash = committed[sequence]
        if event.get("previous_sequence") != sequence - 1 or event.get("previous_head") != previous_head:
            raise AdwError(8, "integrity_hold", "audit chain continuity is broken")
        if previous_manifest is not None:
            for name in ("state.md", "evidence.md"):
                if manifest["targets"][name]["before_hash"] != previous_manifest["targets"][name]["staged_hash"]:
                    raise AdwError(8, "integrity_hold", "transaction before-image does not match prior committed target")
        staged_state = ControlBlock.parse(_read_no_follow(transaction / "staged" / "state.md")).value
        policies = (staged_state["write_policy"], staged_state["loop_policy"])
        if base_policies is None:
            base_policies = policies
        elif policies != base_policies:
            raise AdwError(8, "integrity_hold", "immutable policy snapshot changed in audit history")
        previous_head = event_hash
        previous_manifest = manifest
    last_transaction, last_manifest, last_marker, last_event, last_head = committed[final_sequence]
    expected_audit = {
        "sequence": final_sequence,
        "head": last_head,
        "last_transaction_id": last_event["transaction_id"],
        "last_request_id": last_event["request_id"],
    }
    if current_state["audit"] != expected_audit or current_evidence["audit"] != expected_audit:
        raise AdwError(8, "integrity_hold", "current Control Blocks do not match the committed audit head")
    for name in ("state.md", "evidence.md"):
        if _sha256(_read_no_follow(item / name)) != last_manifest["targets"][name]["staged_hash"]:
            raise AdwError(8, "integrity_hold", "current target does not match the committed head")


def read_consistent_snapshot(item, now=None) -> CommittedSnapshot:
    """Read one fully committed snapshot, retrying once if dependencies move."""

    item = _safe_work_item_layout(item)
    ensure_local_filesystem(item)
    current_time = now or datetime.now(timezone.utc)
    for attempt in range(2):
        try:
            before = _snapshot_fingerprint(item)
            _reject_active_locks(item, current_time)
            state = ControlBlock.parse(_read_no_follow(item / "state.md")).value
            evidence = ControlBlock.parse(_read_no_follow(item / "evidence.md")).value
            validate_control_pair(state, evidence)
            _validate_committed_journal(item, state, evidence)
            _reject_active_locks(item, current_time)
            after = _snapshot_fingerprint(item)
        except FileNotFoundError:
            before = after = None
        if before is not None and before == after:
            token = _sha256(canonical_json({"work_item": state["work_item"], "audit": state["audit"]}))
            return CommittedSnapshot(state, evidence, dict(state["audit"]), token)
        if attempt == 1:
            raise AdwError(6, "busy", "snapshot changed during two read attempts")
    raise AdwError(6, "busy", "snapshot could not be read consistently")


def validate_tdd_evidence_selection(snapshot, work_item, green_ids, red_ids):
    """Require real, ordered, intact RED and GREEN command evidence for TDD acceptance."""

    records = {
        record.get("id"): record for record in snapshot.evidence["evidence_index"]
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    red = [records.get(evidence_id) for evidence_id in red_ids]
    green = [records.get(evidence_id) for evidence_id in green_ids]
    valid_red = red and all(
        record is not None and record.get("type") == "command_result"
        and record.get("state") == "TDD" and record.get("result_status") == "fail"
        and record.get("validity_status") == "current"
        for record in red
    )
    valid_green = green and all(
        record is not None and record.get("type") == "command_result"
        and record.get("state") == "TDD" and record.get("result_status") == "pass"
        and record.get("validity_status") == "current"
        for record in green
    )
    if not valid_red or not valid_green or set(green_ids) & set(red_ids):
        raise AdwError(4, "incomplete_evidence", "TDD acceptance requires distinct current RED and GREEN command evidence")
    change_revision = snapshot.state["current_revisions"]["change"]
    if change_revision is None:
        raise AdwError(4, "incomplete_evidence", "TDD acceptance requires a recorded change revision")
    if any(record.get("input_revisions", {}).get("change") != change_revision for record in green):
        raise AdwError(4, "incomplete_evidence", "TDD GREEN evidence must be bound to the current change revision")
    try:
        red_times = [_parse_utc(record["observed_at"]) for record in red]
        green_times = [_parse_utc(record["observed_at"]) for record in green]
    except (KeyError, TypeError, ValueError):
        raise AdwError(4, "incomplete_evidence", "TDD command evidence time is invalid")
    if max(red_times) >= min(green_times):
        raise AdwError(4, "incomplete_evidence", "TDD RED evidence must precede GREEN evidence")
    for record in red + green:
        verify_artifact(work_item, record["artifact_ref"], record["integrity_ref"])


SPECIFICATION_PACKAGE_DOCUMENTS = (
    "01-scope.md",
    "02-investigation.md",
    "03-roadmap.md",
    "04-code-guide.md",
    "specification.md",
)
WORK_ITEM_DOCUMENTS = (
    "state.md",
    *SPECIFICATION_PACKAGE_DOCUMENTS,
    "evidence.md",
    "review.md",
    "completion.md",
)
_MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _safe_runtime_text(value, name):
    if not isinstance(value, str) or not value or len(value) > 128 or any(ord(char) < 32 for char in value):
        raise AdwError(2, "invalid_input", "%s is not safe runtime text" % name)


def _safe_reference(value, name):
    _safe_runtime_text(value, name)
    if value.startswith(("/", "~")) or ".." in Path(value).parts or re.search(r"(?i)(secret|password|token|cookie|authorization)", value):
        raise AdwError(2, "invalid_input", "%s is not a safe reference" % name)


def _load_bundled_runtime_policy():
    assets = Path(__file__).resolve().parent.parent / "assets"
    path = assets / "runtime-policy.json"
    if assets.is_symlink() or not assets.is_dir() or path.is_symlink() or not path.is_file():
        raise AdwError(4, "invalid_configuration", "bundled runtime policy is missing or unsafe")
    try:
        value = json.loads(_read_no_follow(path).decode("utf-8"), object_pairs_hook=_strict_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise AdwError(4, "invalid_configuration", "bundled runtime policy is not strict JSON")
    expected = {"schema_version", "profile_suffix", "write_policy", "loop_policy"}
    if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != 1:
        raise AdwError(4, "invalid_configuration", "bundled runtime policy fields are invalid")
    _safe_runtime_text(value["profile_suffix"], "configuration profile suffix")
    templates = assets / "templates"
    if templates.is_symlink() or not templates.is_dir():
        raise AdwError(4, "invalid_configuration", "bundled template root is missing or unsafe")
    for name in WORK_ITEM_DOCUMENTS:
        template = templates / name
        if template.is_symlink() or not template.is_file():
            raise AdwError(4, "invalid_configuration", "required bundled work-item template is missing")
    _validate_write_policy(value["write_policy"])
    _validate_loop_policy(value["loop_policy"])
    value["template_root"] = templates.resolve()
    return value


def _safe_delivery_root(value):
    root = Path(value)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        _unsafe("delivery root must be an existing absolute non-symlink directory")
    return root.resolve()


def _intake_ticket(item):
    if item.is_symlink() or not item.is_dir():
        _unsafe("ticket directory must be a non-symlink directory")
    entries = list(item.iterdir())
    if (
        len(entries) != 1 or entries[0].name in set(WORK_ITEM_DOCUMENTS) | {".adw", "artifacts"}
        or entries[0].is_symlink() or not entries[0].is_file()
    ):
        raise AdwError(5, "existing_destination", "existing ticket directory is not intake-only")
    _safe_runtime_text(entries[0].name, "ticket source name")
    if "`" in entries[0].name:
        raise AdwError(2, "invalid_input", "ticket source name is unsafe for the approval package")
    return entries[0].name, _read_no_follow(entries[0])


def _initialization_lock(root, ticket_id):
    path = root / (".%s.init.lock" % ticket_id)
    descriptor = -1
    try:
        descriptor = os.open(str(path), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), 0o600)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise AdwError(8, "integrity_hold", "initialization lock is not a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except (BlockingIOError, OSError) as exc:
        if descriptor >= 0:
            os.close(descriptor)
        if isinstance(exc, BlockingIOError):
            raise AdwError(6, "busy", "ticket initialization is already in progress")
        raise AdwError(8, "integrity_hold", "initialization lock is unsafe: %s" % exc)
    except AdwError:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _discard_initialization_staging(staging):
    """Remove only regular files/directories that this failed local init staged."""

    for directory, directories, files in os.walk(str(staging), topdown=False, followlinks=False):
        current = Path(directory)
        for name in files:
            path = current / name
            if not path.is_symlink() and path.is_file():
                path.unlink()
        for name in directories:
            path = current / name
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    staging.rmdir()


def _render_template(raw, ticket_id, repository, owner):
    title = (ticket_id + " — Ticket intake").encode("utf-8")
    rendered = raw.replace(b"TICKET-ID", ticket_id.encode("utf-8"))
    rendered = rendered.replace(b"repository-name", repository.encode("utf-8"))
    rendered = rendered.replace(b"ticket-owner", owner.encode("utf-8"))
    rendered = rendered.replace(b"[Ticket ID \xe2\x80\x94 Title]", b"[" + title + b"]")
    return rendered


def _validate_generated_links(item, documents):
    for name, raw in documents.items():
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise AdwError(4, "invalid_template", "%s is not UTF-8 Markdown" % name)
        for match in _MARKDOWN_LINK.finditer(text):
            target = match.group(1).split("#", 1)[0]
            if not target or ":" in target:
                continue
            relative = Path(target)
            if not relative.is_absolute() and ".." not in relative.parts and len(relative.parts) == 1 and relative.name in documents:
                continue
            path = (item / target).resolve()
            try:
                contained = os.path.commonpath([str(path), str(item.parent.parent)]) == str(item.parent.parent)
            except ValueError:
                contained = False
            if not contained or not path.is_file() or path.is_symlink():
                raise AdwError(4, "invalid_template", "generated link in %s is invalid" % name)


def _write_genesis(item, documents, runtime_configuration, ticket_id, repository, owner, configuration, request_id, lead_run_ref, now):
    state_document = ControlBlock.parse(documents["state.md"])
    evidence_document = ControlBlock.parse(documents["evidence.md"])
    state = _normalize_json(state_document.value)
    evidence = _normalize_json(evidence_document.value)
    state.update({
        "work_item": ticket_id,
        "repository": repository,
        "state": "SPECIFY",
        "review_pass": None,
        "blocked_from_state": None,
        "blocked_from_review_pass": None,
        "resume_state": None,
        "resume_review_pass": None,
        "owner": owner,
        "required_evidence_ids": [],
        "current_revisions": {name: None for name in REVISION_FIELDS},
        "revision_history": [],
        "gate_evidence": {name: None for name in GATE_FIELDS},
        "transition_history": [],
        "blocker_ids": [],
        "exception_ids": [],
        "write_policy": _normalize_json(configuration["write_policy"]),
        "loop_policy": _normalize_json(configuration["loop_policy"]),
    })
    audit = {"sequence": 1, "head": None, "last_transaction_id": "INIT-" + secrets.token_hex(12), "last_request_id": request_id}
    state["audit"] = dict(audit)
    evidence.update({"work_item": ticket_id, "audit": dict(audit), "evidence_index": []})
    state_projection = _control_projection(state)
    evidence_projection = _control_projection(evidence)
    safe_arguments = {"ticket_id": ticket_id, "repository": repository, "owner": owner, "profile": configuration["profile"]}
    transaction_id = audit["last_transaction_id"]
    observed = _utc_text(now)
    event = {
        "schema": 1, "work_item": ticket_id, "sequence": 1, "transaction_id": transaction_id,
        "request_id": request_id, "command": "init",
        "safe_argument_hash": _sha256(canonical_json({"command": "init", "safe_arguments": safe_arguments})),
        "recorded_by": lead_run_ref, "started_at": observed, "prepared_at": observed,
        "previous_sequence": 0, "previous_head": None,
        "affected_control_blocks": ["evidence.md", "state.md"], "semantic_ids": [], "artifacts": [],
        "control_block_hashes": {
            "state.md": {"before": None, "after": _sha256(canonical_json(state_projection))},
            "evidence.md": {"before": None, "after": _sha256(canonical_json(evidence_projection))},
        },
        "narrative_hashes": {
            "state.md": {"before": None, "after": _sha256(state_document.narrative)},
            "evidence.md": {"before": None, "after": _sha256(evidence_document.narrative)},
        },
        "intended_result": {
            "work_item_path": str(item), "state": "SPECIFY",
            "runtime_configuration_sha256": _sha256(runtime_configuration),
        },
    }
    head = _sha256(canonical_json(event))
    state["audit"]["head"] = head
    evidence["audit"]["head"] = head
    validate_control_pair(state, evidence)
    final_documents = dict(documents)
    final_documents["state.md"] = state_document.replace(state)
    final_documents["evidence.md"] = evidence_document.replace(evidence)
    target_hashes = {name: _sha256(final_documents[name]) for name in ("state.md", "evidence.md")}
    marker = {
        "schema": 1, "work_item": ticket_id, "sequence": 1, "transaction_id": transaction_id,
        "request_id": request_id, "event_hash": head,
        "result_hash": _sha256(canonical_json(event["intended_result"])), "target_hashes": target_hashes,
        "artifact_hashes": {}, "outcome": "committed", "commit_recorded_at": observed,
    }
    manifest = {
        "schema": 1, "work_item": ticket_id, "sequence": 1, "transaction_id": transaction_id,
        "request_id": request_id, "command_input_hash": event["safe_argument_hash"], "event_hash": head,
        "expected_commit_marker_hash": _sha256(canonical_json(marker)),
        "targets": {name: {"before_hash": None, "staged_hash": digest} for name, digest in target_hashes.items()},
        "artifacts": {},
    }
    for name, data in final_documents.items():
        _write_new(item / name, data)
    (item / "artifacts").mkdir(mode=0o700)
    transaction = item / ".adw" / "transactions" / ("1-" + transaction_id)
    for directory in (item / ".adw", item / ".adw" / "transactions", transaction, transaction / "before", transaction / "staged", transaction / "staged" / "artifacts", transaction / "recovery-events"):
        directory.mkdir(mode=0o700)
    _write_new(item / ".adw" / "runtime-configuration.json", runtime_configuration)
    for name in ("state.md", "evidence.md"):
        _write_new(transaction / "staged" / name, final_documents[name])
    _write_new(transaction / "audit-event.json", canonical_json(event))
    _write_new(transaction / "manifest.json", canonical_json(manifest))
    marker_bytes = canonical_json(marker)
    _write_new(transaction / "staged" / "commit-marker.json", marker_bytes)
    _write_new(transaction / "commit.json", marker_bytes)
    for directory in (transaction / "staged", transaction, item / ".adw" / "transactions", item / ".adw", item):
        _fsync_directory(directory)
    return {"work_item_path": str(item), "audit": dict(state["audit"])}


def init_work_item(ticket_id, repository, owner, delivery_root, request_id, lead_run_ref, now=None):
    """Safely establish a SPECIFY work item from absent or ticket-first intake."""

    _path_identifier(ticket_id, "ticket_id")
    for value, name in ((repository, "repository"), (owner, "owner"), (request_id, "request_id"), (lead_run_ref, "lead_run_ref")):
        _safe_runtime_text(value, name)
    policy = _load_bundled_runtime_policy()
    root = _safe_delivery_root(delivery_root)
    profile = repository + "-" + policy["profile_suffix"]
    _safe_runtime_text(profile, "configuration profile")
    configuration = {
        "profile": profile,
        "write_policy": policy["write_policy"],
        "loop_policy": policy["loop_policy"],
    }
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        _invalid("initialization time must be timezone-aware")
    destination = root / ticket_id
    lock = _initialization_lock(root, ticket_id)
    staging = None
    backup = None
    try:
        if destination.exists() or destination.is_symlink():
            intake_name, intake_bytes = _intake_ticket(destination)
            intake = True
        else:
            intake_name = None
            intake_bytes = None
            intake = False
        while True:
            staging = root / (".%s.init-%s" % (ticket_id, secrets.token_hex(12)))
            try:
                staging.mkdir(mode=0o700)
                break
            except FileExistsError:
                continue
        documents = {}
        template_fingerprints = {}
        for name in WORK_ITEM_DOCUMENTS:
            raw = _read_no_follow(policy["template_root"] / name)
            template_fingerprints[name] = _sha256(raw)
            documents[name] = _render_template(raw, ticket_id, repository, owner)
        _validate_generated_links(staging, documents)
        if intake:
            _write_new(staging / intake_name, intake_bytes)
        runtime_configuration = {
            "schema_version": 1,
            "profile": profile,
            "repository": repository,
            "delivery_root": str(root),
            "template_source": "bundled",
            "template_fingerprints": template_fingerprints,
            "write_policy": policy["write_policy"],
            "loop_policy": policy["loop_policy"],
        }
        result = _write_genesis(
            staging, documents, canonical_json(runtime_configuration), ticket_id, repository, owner,
            configuration, request_id, lead_run_ref, current_time,
        )
        ensure_local_filesystem(staging)
        if intake:
            if _intake_ticket(destination) != (intake_name, intake_bytes):
                raise AdwError(5, "state_conflict", "ticket input changed during initialization")
            backup = root / (".%s.intake-backup-%s" % (ticket_id, secrets.token_hex(12)))
            os.rename(str(destination), str(backup))
            try:
                os.rename(str(staging), str(destination))
                if _read_no_follow(destination / intake_name) != intake_bytes:
                    os.rename(str(destination), str(staging))
                    os.rename(str(backup), str(destination))
                    backup = None
                    raise AdwError(8, "integrity_hold", "published ticket input bytes changed")
                staging = None
            except OSError as exc:
                if backup is not None and backup.exists() and not destination.exists():
                    os.rename(str(backup), str(destination))
                    backup = None
                raise AdwError(8, "integrity_hold", "ticket-first publication failed safely: %s" % exc)
            os.unlink(str(backup / intake_name))
            os.rmdir(str(backup))
            backup = None
        else:
            if destination.exists() or destination.is_symlink():
                raise AdwError(5, "existing_destination", "ticket directory was created during initialization")
            try:
                os.rename(str(staging), str(destination))
                staging = None
            except OSError as exc:
                raise AdwError(5, "existing_destination", "ticket directory could not be published: %s" % exc)
        _fsync_directory(root)
        result["work_item_path"] = str(destination)
        result["runtime_configuration_path"] = str(destination / ".adw" / "runtime-configuration.json")
        return result
    finally:
        if staging is not None and staging.exists() and not staging.is_symlink():
            _discard_initialization_staging(staging)
        os.close(lock)


def status_work_item(work_item, delivery_root):
    """Return a deliberately small, Control-Block-only safe status snapshot."""

    item = resolve_work_item(delivery_root, work_item)
    snapshot = read_consistent_snapshot(item)
    state = snapshot.state
    return {
        "work_item": state["work_item"], "repository": state["repository"], "owner": state["owner"],
        "state": state["state"], "review_pass": state["review_pass"],
        "audit_sequence": snapshot.audit["sequence"], "audit_head": snapshot.audit["head"],
        "transaction_id": snapshot.audit["last_transaction_id"], "snapshot_token": snapshot.token,
        "gate_evidence": dict(state["gate_evidence"]), "blocker_ids": list(state["blocker_ids"]),
        "loop_policy_revision": state["loop_policy"]["policy_revision"],
        "specification_revision": state["current_revisions"]["specification"],
        "current_revisions": dict(state["current_revisions"]),
        "last_transition": copy.deepcopy(state["transition_history"][-1]) if state["transition_history"] else None,
    }


def _has_preserved_write_lease(transaction: Path, event: Dict[str, Any], now: datetime) -> bool:
    """Accept only the original write-lease evidence preserved by an earlier recovery."""

    events = transaction / "recovery-events"
    if events.is_symlink() or not events.is_dir():
        raise AdwError(8, "integrity_hold", "recovery evidence directory is invalid")
    matches = []
    for path in events.iterdir():
        if path.name.startswith("stale-write-"):
            if path.is_symlink() or not path.is_dir():
                raise AdwError(8, "integrity_hold", "preserved write lease is unsafe")
            matches.append(path)
    if not matches:
        return False
    if len(matches) != 1:
        raise AdwError(8, "integrity_hold", "prepared transaction has ambiguous preserved write leases")
    owner_path = matches[0] / "owner.json"
    flock_path = matches[0] / "owner.flock"
    if owner_path.is_symlink() or flock_path.is_symlink() or not owner_path.is_file() or not flock_path.is_file():
        raise AdwError(8, "integrity_hold", "preserved write lease evidence is incomplete")
    try:
        metadata = _read_canonical_object(owner_path)
        _validate_owner_metadata(metadata)
        descriptor = os.open(str(flock_path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise AdwError(8, "integrity_hold", "preserved write lease advisory file is unsafe")
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise AdwError(8, "integrity_hold", "preserved write lease evidence is unreadable: %s" % exc)
    if (
        metadata["work_item"] != event.get("work_item")
        or metadata["transaction_id"] != event.get("transaction_id")
        or metadata["request_id"] != event.get("request_id")
        or metadata["base_sequence"] != event.get("previous_sequence")
        or metadata["base_head"] != event.get("previous_head")
        or now < _parse_utc(metadata["expires_at"])
    ):
        raise AdwError(8, "integrity_hold", "preserved write lease does not match the prepared transaction")
    return True


def recover_work_item(work_item, transaction_id, recovery_request_id, lead_run_ref, now=None):
    """Finalize or abort one known transaction without performing its command."""

    _path_identifier(transaction_id, "transaction_id")
    _safe_runtime_text(recovery_request_id, "recovery_request_id")
    _safe_runtime_text(lead_run_ref, "lead_run_ref")
    item = _safe_work_item_layout(work_item)
    ensure_local_filesystem(item)
    current_time = now or datetime.now(timezone.utc)
    transactions = item / ".adw" / "transactions"
    matches = []
    for path in transactions.iterdir():
        if path.is_symlink() or not path.is_dir():
            raise AdwError(8, "integrity_hold", "transaction journal contains an unsafe entry")
        event_path = path / "audit-event.json"
        if event_path.is_file() and not event_path.is_symlink():
            event = _read_canonical_object(event_path)
            if event.get("transaction_id") == transaction_id:
                matches.append((path, event))
    if len(matches) != 1:
        raise AdwError(2, "invalid_input", "recovery transaction identity is unknown or ambiguous")
    transaction, event = matches[0]
    manifest = _read_canonical_object(transaction / "manifest.json")
    if manifest.get("transaction_id") != transaction_id or manifest.get("event_hash") != _sha256(canonical_json(event)):
        raise AdwError(8, "integrity_hold", "recovery transaction metadata is inconsistent")
    abort_path = transaction / "abort.json"
    commit_path = transaction / "commit.json"
    if abort_path.exists() and commit_path.exists():
        raise AdwError(8, "integrity_hold", "recovery transaction has conflicting terminal markers")
    aborted = abort_path.is_file()
    if aborted:
        _validate_aborted_transaction(transaction, manifest)
    before_state = ControlBlock.parse(_read_no_follow(transaction / "before" / "state.md")).value
    before_evidence = ControlBlock.parse(_read_no_follow(transaction / "before" / "evidence.md")).value
    validate_control_pair(before_state, before_evidence)
    write_lock_path = item / ".adw" / "write.lock"
    write_lock_exists = write_lock_path.exists() or write_lock_path.is_symlink()
    if not write_lock_exists and not commit_path.is_file() and not aborted and not _has_preserved_write_lease(transaction, event, current_time):
        raise AdwError(8, "recovery_required", "prepared transaction has no write lock to recover")
    recovery_claim = None
    try:
        recovery_lock = LeaseLock.acquire(
            item, "recovery", before_state["work_item"], "RECOVERY-" + secrets.token_hex(10),
            recovery_request_id, before_state["audit"]["sequence"], before_state["audit"]["head"],
            lead_run_ref, before_state["write_policy"]["lock_lease_seconds"], now=current_time,
        )
    except AdwError as error:
        if error.kind != "recovery_required":
            raise
        recovery_claim = LeaseLock.claim_expired(item, "recovery", transaction / "recovery-events", now=current_time)
        try:
            recovery_lock = LeaseLock.acquire(
                item, "recovery", before_state["work_item"], "RECOVERY-" + secrets.token_hex(10),
                recovery_request_id, before_state["audit"]["sequence"], before_state["audit"]["head"],
                lead_run_ref, before_state["write_policy"]["lock_lease_seconds"], now=current_time,
            )
        except Exception:
            recovery_claim.close()
            raise
    claim = None
    try:
        if write_lock_exists:
            claim = LeaseLock.claim_expired(item, "write", transaction / "recovery-events", now=current_time)
        if write_lock_path.exists() or write_lock_path.is_symlink():
            raise AdwError(8, "integrity_hold", "stale write lock was not preserved")
        if commit_path.is_file() or aborted:
            current_state = ControlBlock.parse(_read_no_follow(item / "state.md")).value
            current_evidence = ControlBlock.parse(_read_no_follow(item / "evidence.md")).value
            validate_control_pair(current_state, current_evidence)
            _validate_committed_journal(item, current_state, current_evidence)
            if aborted:
                return {"status": "aborted", "transaction_id": transaction_id, "request_id": event["request_id"]}
            return {"status": "committed", "transaction_id": transaction_id, "request_id": event["request_id"], "result": event["intended_result"]}
        artifact_hashes = manifest.get("artifacts")
        if not isinstance(artifact_hashes, dict) or any(
            not isinstance(name, str) or not isinstance(digest, str)
            for name, digest in artifact_hashes.items()
        ):
            raise AdwError(8, "integrity_hold", "recovery artifact manifest is malformed")
        artifacts = {}
        for name, digest in artifact_hashes.items():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("artifacts",):
                raise AdwError(8, "integrity_hold", "recovery artifact path is unsafe")
            try:
                staged = _contained_artifact_target(transaction / "staged", name)
                data = _read_no_follow(staged)
            except (AdwError, OSError) as error:
                raise AdwError(8, "integrity_hold", "recovery staged artifact is unsafe: %s" % error)
            if _sha256(data) != digest:
                raise AdwError(8, "integrity_hold", "recovery staged artifact hash is invalid")
            artifacts[name] = data
        prepared = PreparedTransaction(
            {name: _read_no_follow(transaction / "before" / name) for name in ("state.md", "evidence.md")},
            {name: _read_no_follow(transaction / "staged" / name) for name in ("state.md", "evidence.md")},
            artifacts, event, _read_canonical_object(transaction / "staged" / "commit-marker.json"), manifest,
        )
        replaced = []
        for name in ("state.md", "evidence.md"):
            current_hash = _sha256(_read_no_follow(item / name))
            target = manifest.get("targets", {}).get(name, {})
            if current_hash == target.get("staged_hash"):
                replaced.append(name)
            elif current_hash != target.get("before_hash"):
                raise AdwError(8, "integrity_hold", "recovery target has an unexpected third hash")
        published = []
        for name, digest in artifact_hashes.items():
            try:
                target = _contained_artifact_target(item, name)
            except AdwError as error:
                raise AdwError(8, "integrity_hold", "recovery artifact target is unsafe: %s" % error)
            if target.exists():
                if target.is_symlink() or _sha256(_read_no_follow(target)) != digest:
                    raise AdwError(8, "integrity_hold", "recovery artifact has an unexpected hash")
                published.append(name)
        _rollback_transaction(item, transaction, prepared, replaced, published, AdwError(8, "recovered", "explicit recovery"), current_time)
        return {"status": "aborted", "transaction_id": transaction_id, "request_id": event["request_id"]}
    finally:
        if claim is not None:
            claim.close()
        if recovery_claim is not None:
            recovery_claim.close()
        recovery_lock.release()


def _incomplete_test_design(message):
    raise AdwError(4, "incomplete_test_design", message)


def _validate_director2_test_design_snapshot(work_item, repository, source_ref):
    """Reject unsupported Director2 harness instructions before they become a revision."""

    if Path(repository).name != "director2-aws":
        return
    try:
        text = _read_no_follow(_contained_artifact_target(Path(work_item), source_ref)).decode("utf-8")
    except UnicodeDecodeError:
        _incomplete_test_design("Director2 test-design snapshot must be UTF-8")
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in (
        r"\bjenkins\b", r"\bnon[- ]root\b", r"\bstandalone-copy-trunk\b",
        r"\bdocker\s+exec\b[^\n]*(?:--user(?:=|\s)|\s-u(?:\s|=))",
    )):
        _incomplete_test_design("Director2 test design contains an unsupported container execution claim")
    harness_selected = "run-harness-sidecar.sh" in text
    targets = re.findall(
        r"(?<![A-Za-z0-9._/-])(/?(?:suite/)?[A-Za-z0-9_-][A-Za-z0-9._-]*/test/[A-Za-z0-9_-][A-Za-z0-9._-]*\.xml)\b",
        text,
    )
    if harness_selected and "director2-harness-test" not in text:
        _incomplete_test_design("Director2 harness test design must name the director2-harness-test capability")
    if harness_selected and not targets:
        _incomplete_test_design("Director2 harness test design must name a harness target")
    for target in targets:
        canonical_target = target.lstrip("/")
        if not canonical_target.startswith("suite/"):
            canonical_target = "suite/" + canonical_target
        root = Path(repository)
        if root.is_absolute() and not (root / "director2" / canonical_target).is_file():
            _incomplete_test_design("Director2 harness target does not exist in the configured repository")


def approved_test_design_command(snapshot, work_item, source_ref):
    """Return one exact command declared by the current immutable test design."""

    if not isinstance(source_ref, str) or not re.fullmatch(r"command:[A-Za-z0-9][A-Za-z0-9._-]{0,63}", source_ref):
        raise AdwError(2, "invalid_input", "evidence command must use command:<approved-id> source reference")
    revision = snapshot.state["current_revisions"].get("test_design")
    entries = [
        entry for entry in snapshot.state["revision_history"]
        if entry.get("domain") == "test_design" and entry.get("id") == revision
    ]
    if not isinstance(revision, str) or len(entries) != 1:
        raise AdwError(2, "invalid_input", "a current immutable test-design command registry is required")
    entry = entries[0]
    verify_artifact(work_item, entry["source_ref"], entry["fingerprint"])
    try:
        text = _read_no_follow(_contained_artifact_target(Path(work_item), entry["source_ref"])).decode("utf-8")
    except UnicodeDecodeError:
        raise AdwError(2, "invalid_input", "test-design command registry must be UTF-8")
    matches = re.findall(r"```adw-command-registry\s*\n(.*?)\n```", text, re.DOTALL)
    if len(matches) != 1:
        raise AdwError(2, "invalid_input", "test design must contain exactly one adw-command-registry block")
    try:
        registry = json.loads(matches[0], object_pairs_hook=_strict_object, parse_constant=_reject_constant)
    except (ValueError, json.JSONDecodeError):
        raise AdwError(2, "invalid_input", "test-design command registry must be strict JSON")
    commands = registry.get("commands") if isinstance(registry, dict) and set(registry) == {"commands"} else None
    command = commands.get(source_ref.split(":", 1)[1]) if isinstance(commands, dict) else None
    if not isinstance(command, dict) or set(command) != {"argv", "expected_exit_codes", "timeout_seconds"}:
        raise AdwError(2, "invalid_input", "evidence command is not approved by the current test design")
    argv = command["argv"]
    exits = command["expected_exit_codes"]
    timeout = command["timeout_seconds"]
    if (
        not isinstance(argv, list) or not argv or any(not isinstance(value, str) or not value for value in argv)
        or not isinstance(exits, list) or not exits or any(isinstance(value, bool) or not isinstance(value, int) for value in exits)
        or isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 1800
    ):
        raise AdwError(2, "invalid_input", "test-design command registry entry is invalid")
    return {"argv": list(argv), "expected_exit_codes": sorted(set(exits)), "timeout_seconds": timeout}


def record_revision(work_item, domain, source_ref, fingerprint, reason, request_id, expected_sequence, expected_head, lead_run_ref, now=None):
    """Record one revision-domain change through the common atomic journal."""

    if domain not in REVISION_FIELDS:
        raise AdwError(2, "invalid_input", "revision domain is invalid")
    if domain == "specification":
        raise AdwError(2, "invalid_input", "use record-specification for the complete specification package")
    _safe_reference(source_ref, "source_ref")
    _safe_runtime_text(reason, "reason")
    _safe_runtime_text(request_id, "request_id")
    _safe_runtime_text(lead_run_ref, "lead_run_ref")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint):
        raise AdwError(2, "invalid_input", "revision fingerprint must be a SHA-256 reference")
    snapshot_prefix = {"specification": "artifacts/specification/", "test_design": "artifacts/test-design/"}.get(domain)
    if snapshot_prefix is not None:
        if not source_ref.startswith(snapshot_prefix):
            raise AdwError(2, "invalid_input", "%s revision requires its immutable snapshot artifact" % domain)
        verify_artifact(work_item, source_ref, fingerprint)

    snapshot = read_consistent_snapshot(work_item)
    if snapshot.audit["sequence"] != expected_sequence or snapshot.audit["head"] != expected_head:
        raise AdwError(5, "stale_snapshot", "expected audit identity is stale")
    if domain == "test_design":
        _validate_director2_test_design_snapshot(work_item, snapshot.state["repository"], source_ref)
    prior = snapshot.state["current_revisions"][domain]
    if any(
        entry.get("domain") == domain and entry.get("source_ref") == source_ref and entry.get("fingerprint") == fingerprint
        for entry in snapshot.state["revision_history"]
    ):
        raise AdwError(2, "invalid_input", "revision source and fingerprint are already current or historical")
    revision_id = "REV-" + secrets.token_hex(12)
    recorded_at = _utc_text(now or datetime.now(timezone.utc))
    state = copy.deepcopy(snapshot.state)
    evidence = copy.deepcopy(snapshot.evidence)
    state["current_revisions"][domain] = revision_id
    state["revision_history"].append({
        "id": revision_id, "domain": domain, "source_ref": source_ref, "fingerprint": fingerprint,
        "reason": reason, "recorded_at": recorded_at, "recorder": lead_run_ref, "prior_revision": prior,
    })
    if prior is not None:
        for entry in evidence["evidence_index"]:
            if entry.get("validity_status") == "current" and entry.get("input_revisions", {}).get(domain) == prior:
                entry["validity_status"] = "invalidated"
                entry["invalidation_reason"] = "revision %s replaced: %s" % (prior, reason)
    transaction_id = "REVISION-" + secrets.token_hex(12)
    result = commit_transaction(
        work_item, state, evidence, expected_sequence=expected_sequence, expected_head=expected_head,
        transaction_id=transaction_id, request_id=request_id, command="record-revision",
        safe_arguments={"domain": domain, "source_ref": source_ref, "fingerprint": fingerprint, "reason": reason},
        lead_run_ref=lead_run_ref, semantic_ids=[revision_id], intended_result={"revision_id": revision_id, "domain": domain}, now=now,
    )
    return result["result"]


def _incomplete_specification(message):
    raise AdwError(4, "incomplete_specification", message)


def _require_specification_text(text, pattern, message, flags=0):
    if re.search(pattern, text, flags) is None:
        _incomplete_specification(message)


def _read_specification_package(work_item):
    """Read and structurally validate the human-readable pre-code package."""

    item = _safe_work_item_layout(work_item)
    raw_documents = {}
    texts = {}
    for name in SPECIFICATION_PACKAGE_DOCUMENTS:
        path = item / name
        if path.is_symlink() or not path.is_file():
            _incomplete_specification("required specification document is missing: %s" % name)
        raw = _read_no_follow(path)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            _incomplete_specification("specification document is not UTF-8: %s" % name)
        if "<!-- ADW-TEMPLATE" in text:
            _incomplete_specification("specification document is still an uncompleted template: %s" % name)
        raw_documents[name] = raw
        texts[name] = text

    scope = texts["01-scope.md"]
    _require_specification_text(scope, r"(?m)^# Scope Statement\s*$", "scope statement heading is missing")
    for label in ("Ticket", "Repo", "Type", "Goal", "Done when", "Constraints", "Prior context", "Out of scope"):
        _require_specification_text(
            scope, r"(?m)^\*\*%s:\*\*\s+\S.+$" % re.escape(label),
            "scope statement is missing a completed %s field" % label,
        )
    _require_specification_text(
        scope, r"(?m)^## Existing Work and TDD Entry\s*$",
        "scope statement is missing the existing-work and TDD-entry section",
    )
    intake = {}
    for label in ("Ticket implementation at intake", "Ticket tests at intake", "RED strategy", "Baseline evidence"):
        match = re.search(r"(?m)^\*\*%s:\*\*\s+(\S.+)$" % re.escape(label), scope)
        if match is None:
            _incomplete_specification("scope statement is missing a completed %s field" % label)
        intake[label] = match.group(1).strip()
    for label in ("Ticket implementation at intake", "Ticket tests at intake"):
        if intake[label] not in {"none", "present"}:
            _incomplete_specification("%s must be none or present" % label)
    red_strategy = intake["RED strategy"]
    existing_work = "present" in {
        intake["Ticket implementation at intake"], intake["Ticket tests at intake"],
    }
    valid_red_strategy = (
        (red_strategy == "normal-red-first" and not existing_work)
        or (red_strategy == "current-failing-test" and intake["Ticket tests at intake"] == "present")
        or (red_strategy == "isolated-clean-baseline" and existing_work)
        or red_strategy == "blocked"
    )
    if not valid_red_strategy:
        _incomplete_specification("RED strategy %s does not match ticket work at intake" % red_strategy)

    investigation = texts["02-investigation.md"]
    for heading in (
        "Current behavior", "What already exists to reuse", "Where the change lives",
        "What is missing", "Open questions",
    ):
        _require_specification_text(
            investigation, r"(?m)^## %s\s*$" % re.escape(heading),
            "investigation is missing the %s section" % heading,
        )
    _require_specification_text(
        investigation, r"(?m)^###\s+`?[^`\n]+\.[A-Za-z0-9]+:\d+(?:[\-\u2013]\d+)?",
        "investigation must cite verified code with a file path and line number",
    )
    if len(re.findall(r"(?m)^```[^\n]*$", investigation)) < 4:
        _incomplete_specification("investigation must quote current and reusable code blocks")
    _require_specification_text(
        investigation, r"(?mi)^\|\s*File\s*\|\s*Lines\s*\|\s*What changes\s*\|",
        "investigation must map exact change locations",
    )
    if re.search(r"(?i)\b(probably|i think|likely|should be)\b", investigation):
        _incomplete_specification("investigation contains unverified hedge language")

    roadmap = texts["03-roadmap.md"]
    for pattern, message in (
        (r"(?m)^# Plan:", "roadmap heading is missing"),
        (r"(?m)^\*\*North Star:\*\*\s+\S", "roadmap North Star is missing"),
        (r"(?m)^## Steps\s*$", "roadmap steps are missing"),
        (r"(?m)^## Risks\s*$", "roadmap risks are missing"),
        (r"(?mi)^\|\s*#\s*\|\s*Step\s*\|\s*File\(s\)\s*\|\s*Done when\s*\|\s*Status\s*\|", "roadmap done-criteria table is missing"),
        (r"\bRED\b", "roadmap must require failing pre-implementation evidence"),
        (r"\bGREEN\b", "roadmap must require passing post-implementation evidence"),
        (r"(?i)full (affected )?suite", "roadmap must include the affected full suite"),
        (r"(?i)code review", "roadmap must include code review"),
    ):
        _require_specification_text(roadmap, pattern, message)

    guide = texts["04-code-guide.md"]
    for heading in ("Files to change", "Pattern to follow", "What NOT to change", "Config changes"):
        _require_specification_text(
            guide, r"(?m)^## %s\s*$" % re.escape(heading),
            "code guide is missing the %s section" % heading,
        )
    _require_specification_text(guide, r"(?mi)^## .*Test Plan\s*$", "code guide must contain a test plan")
    _require_specification_text(
        guide, r"[A-Za-z0-9_./-]+\.[A-Za-z0-9]+:\d+",
        "code guide must cite the verified implementation pattern",
    )

    specification = texts["specification.md"]
    for heading in (
        "Ticket and Goal", "Scope and Constraints", "Configuration Resolution Record",
        "Specification Package", "Acceptance Criteria", "Gherkin Scenarios", "Approval Record",
    ):
        _require_specification_text(
            specification, r"(?m)^## %s\s*$" % re.escape(heading),
            "specification is missing the %s section" % heading,
        )
    for name in SPECIFICATION_PACKAGE_DOCUMENTS[:-1]:
        if name not in specification:
            _incomplete_specification("specification does not link %s" % name)
    for keyword in ("Scenario:", "Given ", "When ", "Then "):
        if keyword not in specification:
            _incomplete_specification("specification Gherkin is missing %s" % keyword.strip())
    return item, raw_documents


def _specification_package_snapshot(work_item):
    item, documents = _read_specification_package(work_item)
    parts = [
        b"# Specification Package Snapshot\n\n",
        ("Work item: `%s`\n" % item.name).encode("utf-8"),
    ]
    for source in sorted(item.iterdir(), key=lambda path: path.name):
        if source.name in WORK_ITEM_DOCUMENTS or source.name in {".adw", "artifacts"}:
            continue
        if source.is_symlink():
            _incomplete_specification("ticket source is unsafe")
        if source.is_dir():
            continue
        if not source.is_file():
            _incomplete_specification("ticket source is unsafe")
        _safe_runtime_text(source.name, "ticket source name")
        if "`" in source.name:
            _incomplete_specification("ticket source name is unsafe")
        data = _read_no_follow(source)
        heading = ("\n---\n\n## Source: `%s`\n\n" % source.name).encode("utf-8")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            description = (
                "Binary source preserved separately (%d bytes, %s).\n"
                % (len(data), _sha256(data))
            ).encode("utf-8")
            parts.extend((heading, description))
        else:
            parts.extend((heading, data.rstrip(b"\n"), b"\n"))
    for name in SPECIFICATION_PACKAGE_DOCUMENTS:
        parts.extend((
            ("\n---\n\n## Document: `%s`\n\n" % name).encode("utf-8"),
            documents[name].rstrip(b"\n"),
            b"\n",
        ))
    return b"".join(parts)


def record_specification_package(work_item, reason, request_id, expected_sequence, expected_head, lead_run_ref, now=None):
    """Validate, snapshot, and revision the complete pre-code package atomically."""

    for value, name in ((reason, "reason"), (request_id, "request_id"), (lead_run_ref, "lead_run_ref")):
        _safe_runtime_text(value, name)
    snapshot = read_consistent_snapshot(work_item)
    if snapshot.state["state"] != "SPECIFY" or snapshot.state["review_pass"] is not None:
        raise AdwError(4, "invalid_state", "specification package can be recorded only in SPECIFY")
    if snapshot.audit["sequence"] != expected_sequence or snapshot.audit["head"] != expected_head:
        raise AdwError(5, "stale_snapshot", "expected audit identity is stale")
    package = _specification_package_snapshot(work_item)
    fingerprint = _sha256(package)
    source_ref = "artifacts/specification-package-%s.md" % fingerprint.split(":", 1)[1]
    if any(
        entry.get("domain") == "specification" and entry.get("fingerprint") == fingerprint
        for entry in snapshot.state["revision_history"]
    ):
        raise AdwError(2, "invalid_input", "specification package is already current or historical")

    revision_id = "REV-" + secrets.token_hex(12)
    recorded_at = _utc_text(now or datetime.now(timezone.utc))
    state = copy.deepcopy(snapshot.state)
    evidence = copy.deepcopy(snapshot.evidence)
    prior = state["current_revisions"]["specification"]
    state["current_revisions"]["specification"] = revision_id
    state["revision_history"].append({
        "id": revision_id, "domain": "specification", "source_ref": source_ref,
        "fingerprint": fingerprint, "reason": reason, "recorded_at": recorded_at,
        "recorder": lead_run_ref, "prior_revision": prior,
    })
    if prior is not None:
        for entry in evidence["evidence_index"]:
            if entry.get("validity_status") == "current" and entry.get("input_revisions", {}).get("specification") == prior:
                entry["validity_status"] = "invalidated"
                entry["invalidation_reason"] = "revision %s replaced: %s" % (prior, reason)

    transaction_id = "REVISION-" + secrets.token_hex(12)
    intended = {
        "revision_id": revision_id, "domain": "specification", "source_ref": source_ref,
        "fingerprint": fingerprint,
    }
    result = commit_transaction(
        work_item, state, evidence, expected_sequence=expected_sequence, expected_head=expected_head,
        transaction_id=transaction_id, request_id=request_id, command="record-specification",
        safe_arguments={"source_ref": source_ref, "fingerprint": fingerprint, "reason": reason},
        lead_run_ref=lead_run_ref, semantic_ids=[revision_id], intended_result=intended,
        now=now, artifacts={source_ref: package},
    )
    return result["result"]


def _derive_attempt_numbers(evidence_index, root_cause_ids, limit):
    _string_list(root_cause_ids, "root_cause_ids")
    if not root_cause_ids or len(root_cause_ids) != len(set(root_cause_ids)):
        _invalid("correction attempt requires distinct root-cause IDs")
    parents = {}
    known = set()
    replaced = set()
    resolved = set()
    for entry in evidence_index:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "root_cause_record":
            results = entry.get("root_cause_ids", [])
            sources = entry.get("parent_root_cause_ids", [])
            for result in results:
                parents.setdefault(result, set()).update(sources)
            known.update(results)
            if entry.get("root_cause_relation") in {"split", "merge"}:
                replaced.update(sources)
        resolved.update(entry.get("resolved_root_cause_ids", []))
    if any(root not in known or root in replaced or root in resolved for root in root_cause_ids):
        raise AdwError(7, "loop_exhausted", "correction attempt targets an unknown, replaced, or resolved root cause")

    def lineage(root):
        result = {root}
        stack = list(parents.get(root, ()))
        while stack:
            ancestor = stack.pop()
            if ancestor not in result:
                result.add(ancestor)
                stack.extend(parents.get(ancestor, ()))
        return result

    attempts = [entry for entry in evidence_index if isinstance(entry, dict) and entry.get("type") == "correction_attempt"]
    numbers = {}
    for root in root_cause_ids:
        inherited = lineage(root)
        consumed = {entry.get("id") for entry in attempts if inherited.intersection(entry.get("root_cause_ids", []))}
        if len(consumed) >= limit:
            raise AdwError(7, "loop_exhausted", "root-cause correction-attempt budget is exhausted")
        numbers[root] = len(consumed) + 1
    return numbers


def record_evidence(work_item, record, artifact_bytes, authority_verifier, request_id, expected_sequence, expected_head, lead_run_ref, now=None):
    """Append one host-verified evidence record and its immutable artifact atomically."""

    if not isinstance(record, dict) or not isinstance(artifact_bytes, bytes):
        raise AdwError(2, "invalid_input", "evidence record and immutable artifact are required")
    if SECRET_EVIDENCE_PATTERN.search(artifact_bytes.decode("utf-8", "replace")):
        raise AdwError(7, "unsafe_evidence", "evidence artifact contains secret-like material")
    _safe_runtime_text(request_id, "request_id")
    _safe_runtime_text(lead_run_ref, "lead_run_ref")
    snapshot = read_consistent_snapshot(work_item)
    if snapshot.audit["sequence"] != expected_sequence or snapshot.audit["head"] != expected_head:
        raise AdwError(5, "stale_snapshot", "expected audit identity is stale")
    known_ids = {entry.get("id") for entry in snapshot.evidence["evidence_index"] if isinstance(entry, dict)}
    if record.get("id") in known_ids:
        raise AdwError(2, "invalid_input", "evidence ID already exists")
    proof_ref = record.get("producer_proof_ref")
    if isinstance(proof_ref, str) and proof_ref.startswith(("receipt:", "execution:")) and any(
        entry.get("producer_proof_ref") == proof_ref
        for entry in snapshot.evidence["evidence_index"] if isinstance(entry, dict)
    ):
        raise AdwError(7, "authority_required", "producer proof receipt was already consumed")
    if not isinstance(record.get("integrity_ref"), str) or _sha256(artifact_bytes) != record["integrity_ref"]:
        raise AdwError(4, "invalid_control_block", "evidence artifact hash does not match")
    transaction_id = "EVIDENCE-" + secrets.token_hex(12)
    recorded_at = _utc_text(now or datetime.now(timezone.utc))
    candidate = copy.deepcopy(record)
    candidate.update({
        "recorded_at": recorded_at, "recorded_by": lead_run_ref, "audit_sequence": expected_sequence + 1,
        "transaction_id": transaction_id, "request_id": request_id,
    })
    if candidate.get("type") == "correction_attempt":
        if (
            candidate.get("decision") != "correction_attempt_started"
            or candidate.get("producer_role") != "lead_agent"
            or candidate.get("loop_policy_revision") != snapshot.state["loop_policy"]["policy_revision"]
        ):
            _invalid("correction attempt authority or policy binding is invalid")
        candidate["attempt_numbers"] = _derive_attempt_numbers(
            snapshot.evidence["evidence_index"], candidate.get("root_cause_ids"),
            snapshot.state["loop_policy"]["max_attempts_per_root_cause"],
        )
    validate_evidence_record(candidate, snapshot.state["work_item"], snapshot.state["current_revisions"], known_ids)
    if not callable(authority_verifier) or authority_verifier(copy.deepcopy(candidate)) is not True:
        raise AdwError(7, "authority_required", "producer proof is not verified by the host adapter")
    evidence = copy.deepcopy(snapshot.evidence)
    evidence["evidence_index"].append(candidate)
    state = copy.deepcopy(snapshot.state)
    gate = candidate.get("gate")
    if gate is not None:
        prior_gate = state["gate_evidence"][gate]
        if prior_gate is not None and prior_gate not in candidate.get("supersedes", []):
            raise AdwError(4, "invalid_control_block", "replacing a gate requires explicit supersession")
        if prior_gate is not None:
            for entry in evidence["evidence_index"][:-1]:
                if entry.get("id") == prior_gate and entry.get("validity_status") == "current":
                    entry["validity_status"] = "superseded"
        state["gate_evidence"][gate] = candidate["id"]
    result = commit_transaction(
        work_item, state, evidence,
        expected_sequence=expected_sequence, expected_head=expected_head, transaction_id=transaction_id,
        request_id=request_id, command="record-evidence",
        safe_arguments={"evidence_id": candidate["id"], "type": candidate["type"], "artifact_ref": candidate["artifact_ref"]},
        lead_run_ref=lead_run_ref, semantic_ids=[candidate["id"]],
        intended_result={"evidence_id": candidate["id"]}, now=now,
        artifacts={candidate["artifact_ref"]: artifact_bytes},
    )
    return result["result"]


def _invalidate_after_correction(state, evidence, target_state, reason):
    gates = {
        "SPECIFY": tuple(GATE_FIELDS),
        "TEST_DESIGN": ("test_design_pass", "tdd_pass", "first_review", "local_qa_pass", "mutation_decision", "final_review"),
        "TDD": ("tdd_pass", "first_review", "local_qa_pass", "mutation_decision", "final_review"),
    }[target_state]
    revisions = {
        "SPECIFY": ("test_design", "change"),
        "TEST_DESIGN": ("test_design", "change"),
        "TDD": ("change",),
    }[target_state]
    invalidated = {state["gate_evidence"][gate] for gate in gates if state["gate_evidence"][gate] is not None}
    for domain in revisions:
        prior = state["current_revisions"][domain]
        if prior is not None:
            invalidated.update(
                entry.get("id") for entry in evidence["evidence_index"]
                if entry.get("validity_status") == "current" and entry.get("input_revisions", {}).get(domain) == prior
            )
        state["current_revisions"][domain] = None
    invalidation_reason = "invalidated by return to %s: %s" % (target_state, reason)
    for entry in evidence["evidence_index"]:
        if entry.get("id") in invalidated and entry.get("validity_status") == "current":
            entry["validity_status"] = "invalidated"
            entry["invalidation_reason"] = invalidation_reason
    for gate in gates:
        state["gate_evidence"][gate] = None


def route_correction(work_item, target_state, reason, next_action, owner, request_id, expected_sequence, expected_head, lead_run_ref, producer_proof_ref, now=None):
    """Atomically record a lead correction decision and return to an earlier development state."""

    for value, name in (
        (reason, "reason"), (next_action, "next_action"), (owner, "owner"),
        (request_id, "request_id"), (lead_run_ref, "lead_run_ref"), (producer_proof_ref, "producer_proof_ref"),
    ):
        _safe_runtime_text(value, name)
    if not producer_proof_ref.startswith("receipt:lead_call-"):
        raise AdwError(7, "authority_required", "route correction requires its exact lead-call receipt")
    snapshot = read_consistent_snapshot(work_item)
    if snapshot.audit["sequence"] != expected_sequence or snapshot.audit["head"] != expected_head:
        raise AdwError(5, "stale_snapshot", "expected audit identity is stale")
    source = (snapshot.state["state"], snapshot.state["review_pass"])
    target = (target_state, None)
    order = {
        ("SPECIFY", None): 1, ("TEST_DESIGN", None): 2, ("TDD", None): 3,
        ("CODE_QUALITY_GATE", None): 4, ("LOWER_ENV_VERIFY", None): 5,
        ("MUTATION_GATE", None): 6, ("DELIVERY_GATE", None): 7,
    }
    if target not in {("SPECIFY", None), ("TEST_DESIGN", None), ("TDD", None)} or source not in order or order[target] >= order[source]:
        raise AdwError(4, "invalid_transition", "correction target must be an earlier SPECIFY, TEST_DESIGN, or TDD state")

    recorded_at = _utc_text(now or datetime.now(timezone.utc))
    transaction_id = "CORRECTION-" + secrets.token_hex(12)
    evidence_id = "E-ROUTE-" + secrets.token_hex(12)
    decision = "return_to_" + target_state.lower()
    state = copy.deepcopy(snapshot.state)
    evidence = copy.deepcopy(snapshot.evidence)
    _invalidate_after_correction(state, evidence, target_state, reason)
    artifact = canonical_json({
        "schema_version": 1, "work_item": state["work_item"], "decision": decision,
        "from_state": source[0], "from_review_pass": source[1], "to_state": target_state,
        "reason": reason, "next_action": next_action, "owner": owner,
    })
    artifact_ref = "artifacts/evidence/%s.json" % evidence_id
    record = {
        "id": evidence_id, "type": "gate_decision", "work_item": state["work_item"],
        "state": source[0], "review_pass": source[1], "observed_at": recorded_at,
        "recorded_at": recorded_at, "audit_sequence": expected_sequence + 1,
        "transaction_id": transaction_id, "request_id": request_id, "result_status": "pass",
        "validity_status": "current", "producer_role": "lead_agent", "producer_ref": lead_run_ref,
        "producer_proof_ref": producer_proof_ref, "recorded_by": lead_run_ref,
        "source_ref": "workflow:route-correction", "artifact_ref": artifact_ref,
        "integrity_ref": _sha256(artifact),
        "input_revisions": {name: value for name, value in state["current_revisions"].items() if value is not None},
        "supports": [], "historical_supports": [], "revision_transition": None,
        "supersedes": [], "invalidation_reason": None, "decision": decision,
    }
    known_ids = {entry.get("id") for entry in evidence["evidence_index"] if isinstance(entry, dict)}
    validate_evidence_record(record, state["work_item"], state["current_revisions"], known_ids)
    evidence["evidence_index"].append(record)
    state["state"], state["review_pass"], state["owner"] = target_state, None, owner
    state["transition_history"].append({
        "audit_sequence": expected_sequence + 1, "transaction_id": transaction_id, "request_id": request_id,
        "recorded_at": recorded_at, "kind": "correct", "from_state": source[0],
        "from_review_pass": source[1], "to_state": target_state, "to_review_pass": None,
        "decision_evidence_id": evidence_id, "supporting_evidence_ids": [evidence_id],
        "reason": reason, "next_action": next_action, "owner": owner,
        "correction_attempt_ids": [], "correction_loop_sequence": None,
    })
    intended = {
        "work_item": state["work_item"], "state": target_state, "review_pass": None,
        "decision_evidence_id": evidence_id, "audit_sequence": expected_sequence + 1,
    }
    result = commit_transaction(
        work_item, state, evidence, expected_sequence=expected_sequence, expected_head=expected_head,
        transaction_id=transaction_id, request_id=request_id, command="route-correction",
        safe_arguments={"target_state": target_state, "reason": reason, "next_action": next_action, "owner": owner},
        lead_run_ref=lead_run_ref, semantic_ids=[evidence_id], intended_result=intended,
        now=now, artifacts={artifact_ref: artifact},
    )
    return result["result"]


def validate_transition(work_item, target_state, target_review_pass, decision_evidence_id, resume_state=None, resume_review_pass=None, correction_attempt_ids=None):
    """Validate one movement against the committed state identity and return a stale-safe token."""

    snapshot = read_consistent_snapshot(work_item)
    correction_attempt_ids = list(correction_attempt_ids or [])
    _string_list(correction_attempt_ids, "correction_attempt_ids")
    if len(correction_attempt_ids) != len(set(correction_attempt_ids)):
        raise AdwError(4, "invalid_transition", "correction-attempt IDs must be distinct")
    source = (snapshot.state["state"], snapshot.state["review_pass"])
    target = (target_state, target_review_pass)
    if target_state not in STATES or target_review_pass is not None:
        raise AdwError(4, "invalid_transition", "target state identity is invalid")
    if source == target or source[0] == "COMPLETE":
        raise AdwError(4, "invalid_transition", "same-state or terminal movement is forbidden")
    forward = {
        ("SPECIFY", None): (("TEST_DESIGN", None), "specification_approval"),
        ("TEST_DESIGN", None): (("TDD", None), "test_design_pass"),
        ("TDD", None): (("CODE_QUALITY_GATE", None), "tdd_pass"),
        ("CODE_QUALITY_GATE", None): (("LOWER_ENV_VERIFY", None), "first_review"),
        ("LOWER_ENV_VERIFY", None): (("MUTATION_GATE", None), "local_qa_pass"),
        ("MUTATION_GATE", None): (("DELIVERY_GATE", None), "mutation_decision"),
        ("DELIVERY_GATE", None): (("COMPLETE", None), "final_review"),
    }
    gate = None
    kind = None
    correction_loop_sequence = None
    order = {("SPECIFY", None): 1, ("TEST_DESIGN", None): 2, ("TDD", None): 3, ("CODE_QUALITY_GATE", None): 4,
             ("LOWER_ENV_VERIFY", None): 5, ("MUTATION_GATE", None): 6, ("DELIVERY_GATE", None): 7}
    if source in forward and forward[source][0] == target:
        kind, gate = "advance", forward[source][1]
        if snapshot.state["gate_evidence"][gate] != decision_evidence_id:
            raise AdwError(4, "invalid_transition", "required gate decision is missing")
        if source == ("TDD", None):
            corrected = any(entry.get("kind") == "correct" for entry in snapshot.state["transition_history"])
            attempts = {entry.get("id") for entry in snapshot.evidence["evidence_index"] if isinstance(entry, dict) and entry.get("type") == "correction_attempt"}
            submitted = {attempt for entry in snapshot.state["transition_history"] for attempt in entry.get("correction_attempt_ids", [])}
            unsubmitted = attempts - submitted
            if corrected and (not unsubmitted or set(correction_attempt_ids) != unsubmitted):
                raise AdwError(7, "loop_accounting_required", "corrected review submission must name every unsubmitted correction attempt")
            if not corrected and correction_attempt_ids:
                raise AdwError(4, "invalid_transition", "initial review submission cannot claim correction attempts")
            correction_loop_sequence = None
            if corrected:
                used = sum(entry.get("correction_loop_sequence") is not None for entry in snapshot.state["transition_history"])
                if used >= snapshot.state["loop_policy"]["max_review_correction_loops"]:
                    raise AdwError(7, "loop_exhausted", "review correction-loop budget is exhausted")
                correction_loop_sequence = used + 1
        else:
            correction_loop_sequence = None
            if correction_attempt_ids:
                raise AdwError(4, "invalid_transition", "correction attempts apply only to TDD review submission")
    elif target_state == "BLOCKED" and source[0] not in {"BLOCKED", "COMPLETE"}:
        resume = (resume_state, resume_review_pass)
        if resume not in order or source not in order or order[resume] > order[source]:
            raise AdwError(4, "invalid_transition", "blocked resume target must be at or before its origin")
        kind = "block"
    elif source[0] == "BLOCKED":
        if target != (snapshot.state["resume_state"], snapshot.state["resume_review_pass"]):
            raise AdwError(4, "invalid_transition", "resume target does not match the blocker contract")
        kind = "resume"
    else:
        allowed = (
            target == ("SPECIFY", None) and source in order and order[source] >= 2
            or target == ("TEST_DESIGN", None) and source in order and order[source] >= 3
            or target == ("TDD", None) and source in order and order[source] >= 4
        )
        if not allowed:
            raise AdwError(4, "invalid_transition", "movement is not in the transition contract")
        kind = "correct"
    if not isinstance(decision_evidence_id, str) or not decision_evidence_id:
        raise AdwError(4, "invalid_transition", "movement requires decision evidence")
    indexed = [entry for entry in snapshot.evidence["evidence_index"] if isinstance(entry, dict) and entry.get("id") == decision_evidence_id]
    if len(indexed) != 1:
        raise AdwError(4, "invalid_transition", "decision evidence is missing or ambiguous")
    decision_record = indexed[0]
    try:
        known_ids = {entry.get("id") for entry in snapshot.evidence["evidence_index"] if isinstance(entry, dict)}
        validate_evidence_record(decision_record, snapshot.state["work_item"], snapshot.state["current_revisions"], known_ids)
        verify_artifact(work_item, decision_record["artifact_ref"], decision_record["integrity_ref"])
        records_by_id = {}
        for entry in snapshot.evidence["evidence_index"]:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                if entry["id"] in records_by_id:
                    _invalid("evidence IDs are ambiguous")
                records_by_id[entry["id"]] = entry
        direct_supports = [records_by_id[support_id] for support_id in decision_record.get("supports", [])]
        if gate == "first_review":
            required = snapshot.state["gate_evidence"]["tdd_pass"]
            if required is None or required not in decision_record["supports"]:
                _invalid("code-quality gate must directly support the current TDD decision")
        elif gate == "local_qa_pass":
            if not any(support.get("type") in {"command_result", "local_qa_result"} for support in direct_supports):
                _invalid("local QA gate must directly support an executed local verification result")
        elif gate == "mutation_decision":
            if not any(support.get("type") == "mutation_result" for support in direct_supports):
                _invalid("mutation gate must directly support a mutation result")
        elif gate == "final_review":
            required = [
                snapshot.state["gate_evidence"][name]
                for name in ("first_review", "local_qa_pass", "mutation_decision")
            ]
            if any(value is None or value not in decision_record["supports"] for value in required):
                _invalid("delivery gate must directly support current quality, local-QA, and mutation decisions")
        if gate == "tdd_pass":
            validate_tdd_evidence_selection(
                snapshot, work_item,
                decision_record.get("supports", []), decision_record.get("historical_supports", []),
            )
        visiting = set()
        visited = set()

        def validate_supports(record):
            if record["id"] in visiting:
                _invalid("evidence support graph is cyclic")
            if record["id"] in visited:
                return
            visiting.add(record["id"])
            for support_id in record.get("supports", []):
                support = records_by_id.get(support_id)
                if support is None:
                    _invalid("evidence support reference is dangling")
                validate_evidence_record(support, snapshot.state["work_item"], snapshot.state["current_revisions"], known_ids)
                verify_artifact(work_item, support["artifact_ref"], support["integrity_ref"])
                if support["validity_status"] != "current":
                    _invalid("direct evidence support is not current")
                if gate is not None and support["result_status"] not in {"pass", "not_required"}:
                    _invalid("forward gate support is not a passing or protocol-not-required result")
                validate_supports(support)
            visiting.remove(record["id"])
            visited.add(record["id"])

        validate_supports(decision_record)
    except AdwError as error:
        raise AdwError(4, "invalid_transition", "decision evidence is unusable: %s" % error)
    if decision_record["result_status"] != "pass" or decision_record["validity_status"] != "current":
        raise AdwError(4, "invalid_transition", "decision evidence is not a current pass")
    if gate is not None and decision_record.get("gate") != gate:
        raise AdwError(4, "invalid_transition", "decision evidence does not satisfy the required gate")
    expected_route_decision = {"correct": "return_to_" + target_state.lower(), "block": "blocked", "resume": "resume_accepted"}.get(kind)
    if expected_route_decision is not None and decision_record.get("decision") != expected_route_decision:
        raise AdwError(4, "invalid_transition", "decision evidence does not authorize this route")
    payload = {
        "work_item": snapshot.state["work_item"], "sequence": snapshot.audit["sequence"], "head": snapshot.audit["head"],
        "from_state": source[0], "from_review_pass": source[1], "to_state": target[0], "to_review_pass": target[1],
        "kind": kind, "decision_evidence_id": decision_evidence_id,
        "resume_state": resume_state if kind == "block" else None,
        "resume_review_pass": resume_review_pass if kind == "block" else None,
        "correction_attempt_ids": sorted(correction_attempt_ids),
        "correction_loop_sequence": correction_loop_sequence,
        "write_policy_revision": snapshot.state["write_policy"]["policy_revision"],
        "loop_policy_revision": snapshot.state["loop_policy"]["policy_revision"],
    }
    payload["token"] = _sha256(canonical_json(payload))
    return payload


def transition_work_item(work_item, validation_token, reason, next_action, owner, request_id, expected_sequence, expected_head, lead_run_ref, now=None):
    """Commit one previously validated movement after revalidating every token binding."""

    if not isinstance(validation_token, dict):
        raise AdwError(2, "invalid_input", "validation token must be an object")
    supplied = copy.deepcopy(validation_token)
    token_hash = supplied.pop("token", None)
    if token_hash != _sha256(canonical_json(supplied)):
        raise AdwError(4, "invalid_transition", "validation token is malformed")
    for value, name in ((reason, "reason"), (next_action, "next_action"), (owner, "owner"), (request_id, "request_id"), (lead_run_ref, "lead_run_ref")):
        _safe_runtime_text(value, name)
    if supplied.get("sequence") != expected_sequence or supplied.get("head") != expected_head:
        raise AdwError(5, "stale_snapshot", "validation token audit identity is stale")
    fresh = validate_transition(
        work_item, supplied.get("to_state"), supplied.get("to_review_pass"), supplied.get("decision_evidence_id"),
        supplied.get("resume_state"), supplied.get("resume_review_pass"),
        supplied.get("correction_attempt_ids"),
    )
    if fresh != validation_token:
        raise AdwError(5, "stale_snapshot", "validation token no longer matches the committed work item")
    snapshot = read_consistent_snapshot(work_item)
    state = copy.deepcopy(snapshot.state)
    evidence = copy.deepcopy(snapshot.evidence)
    if supplied["kind"] == "correct":
        _invalidate_after_correction(state, evidence, supplied["to_state"], reason)
    state["state"] = supplied["to_state"]
    state["review_pass"] = supplied["to_review_pass"]
    if supplied["kind"] == "block":
        state["blocked_from_state"] = supplied["from_state"]
        state["blocked_from_review_pass"] = supplied["from_review_pass"]
        state["resume_state"] = supplied["resume_state"]
        state["resume_review_pass"] = supplied["resume_review_pass"]
        state["blocker_ids"] = [supplied["decision_evidence_id"]]
    if supplied["kind"] == "resume":
        for field in ("blocked_from_state", "blocked_from_review_pass", "resume_state", "resume_review_pass"):
            state[field] = None
        state["blocker_ids"] = []
    transaction_id = "TRANSITION-" + secrets.token_hex(12)
    recorded_at = _utc_text(now or datetime.now(timezone.utc))
    state["owner"] = owner
    state["transition_history"].append({
        "audit_sequence": expected_sequence + 1, "transaction_id": transaction_id, "request_id": request_id,
        "recorded_at": recorded_at, "kind": supplied["kind"], "from_state": supplied["from_state"],
        "from_review_pass": supplied["from_review_pass"], "to_state": supplied["to_state"],
        "to_review_pass": supplied["to_review_pass"], "decision_evidence_id": supplied["decision_evidence_id"],
        "supporting_evidence_ids": [supplied["decision_evidence_id"]], "reason": reason,
        "next_action": next_action, "owner": owner,
        "correction_attempt_ids": supplied["correction_attempt_ids"],
        "correction_loop_sequence": supplied["correction_loop_sequence"],
    })
    result = commit_transaction(
        work_item, state, evidence, expected_sequence=expected_sequence, expected_head=expected_head,
        transaction_id=transaction_id, request_id=request_id, command="transition",
        safe_arguments={"from_state": supplied["from_state"], "to_state": supplied["to_state"], "kind": supplied["kind"], "decision_evidence_id": supplied["decision_evidence_id"]},
        lead_run_ref=lead_run_ref, semantic_ids=[transaction_id],
        intended_result={"state": supplied["to_state"], "review_pass": supplied["to_review_pass"]}, now=now,
    )
    return result["result"]
