#!/usr/bin/env python3
"""Capture narrow Codex host events as immutable workflow receipts."""

import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path


PLUGIN_ROOT = Path(os.environ.get("PLUGIN_ROOT") or Path(__file__).resolve().parents[1]).resolve()
SCRIPTS = PLUGIN_ROOT / "skills" / "agentic-development-workflow" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from adw_core import AdwError, canonical_json, resolve_work_item  # noqa: E402
from adw_receipts import (  # noqa: E402
    create_receipt, create_specification_approval_request, default_receipt_root,
    find_current_approval_request, find_specification_approval_receipt,
)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_input():
    try:
        value = json.loads(sys.stdin.read(), object_pairs_hook=strict_object)
    except (ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def receipt_root():
    override = os.environ.get("AGENTIC_WORKFLOW_RECEIPT_ROOT")
    return Path(override) if override else default_receipt_root()


def emit(value):
    sys.stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":")))
    sys.stdout.write("\n")


def block(event, reason):
    if event == "PreToolUse":
        emit({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        })
    else:
        emit({"decision": "block", "reason": reason})


def host_fields(payload):
    return (
        payload.get("session_id"), payload.get("turn_id"),
        payload.get("tool_use_id") or payload.get("agent_id") or payload.get("turn_id"),
        payload.get("cwd"),
    )


def _declaration_path(payload):
    session_id = payload.get("session_id")
    cwd = payload.get("cwd")
    if not isinstance(session_id, str) or not session_id or not isinstance(cwd, str) or not cwd:
        return None
    client = os.environ.get("DECLARATION_CLIENT") or "codex"
    slug = lambda value: re.sub(r"[^A-Za-z0-9._-]+", "-", value)  # noqa: E731
    root = Path((os.environ.get("TMPDIR") or "/tmp").rstrip("/")) / "agent-skills-declarations"
    cwd_hash = hashlib.sha256(cwd.encode("utf-8")).hexdigest()[:12]
    return root / ("%s-%s-%s.json" % (slug(client), slug(session_id), cwd_hash))


def _read_declaration(path):
    if path is None or not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("workflow declaration is unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise ValueError("workflow declaration is not strict JSON")
    if (
        not isinstance(value, dict) or not isinstance(value.get("task"), str)
        or not isinstance(value.get("files_to_touch"), list)
        or any(not isinstance(item, str) or not item for item in value["files_to_touch"])
        or not isinstance(value.get("approved"), bool)
    ):
        raise ValueError("workflow declaration structure is invalid")
    return value


def _write_declaration(path, value):
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".workflow-%d.tmp" % os.getpid())
    descriptor = None
    try:
        descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _declaration_scope_sha256(declaration):
    scope = {
        "task": declaration["task"],
        "files_to_touch": declaration["files_to_touch"],
    }
    return "sha256:" + hashlib.sha256(canonical_json(scope)).hexdigest()


def bind_workflow_declaration(payload, request):
    path = _declaration_path(payload)
    declaration = _read_declaration(path)
    if declaration is None:
        return False
    claim = request["claim"]
    work_item_path = Path(claim["work_item_path"]).resolve()
    declared_ticket_file = False
    for item in declaration["files_to_touch"]:
        candidate = Path(item)
        if candidate.is_absolute():
            resolved = candidate.resolve(strict=False)
            if resolved == work_item_path or work_item_path in resolved.parents:
                declared_ticket_file = True
                break
    if not declared_ticket_file:
        raise ValueError("active declaration is not scoped to the prepared workflow ticket")
    artifact_scope = str(work_item_path / "artifacts" / "**")
    if artifact_scope not in declaration["files_to_touch"]:
        declaration["files_to_touch"].append(artifact_scope)
    declaration["approved"] = False
    declaration["workflow_authorization"] = {
        "name": "agentic-development-workflow",
        "work_item": claim["work_item"],
        "work_item_path": claim["work_item_path"],
        "specification_revision": claim["revision"],
        "approval_request_ref": request["ref"],
        "declaration_sha256": _declaration_scope_sha256(declaration),
    }
    _write_declaration(path, declaration)
    return True


def approve_workflow_declaration(payload, request, approval):
    path = _declaration_path(payload)
    declaration = _read_declaration(path)
    if declaration is None:
        return False
    claim = request["claim"]
    expected = {
        "name": "agentic-development-workflow",
        "work_item": claim["work_item"],
        "work_item_path": claim["work_item_path"],
        "specification_revision": claim["revision"],
        "approval_request_ref": request["ref"],
        "declaration_sha256": _declaration_scope_sha256(declaration),
    }
    if declaration.get("workflow_authorization") != expected:
        return False
    declaration["approved"] = True
    declaration["workflow_authorization"] = dict(expected, human_approval_ref=approval["ref"])
    _write_declaration(path, declaration)
    return True


def capture_human(payload):
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return False
    if prompt.strip().casefold() == "i approve":
        session_id, turn_id, event_id, cwd = host_fields(payload)
        try:
            request = find_current_approval_request(receipt_root(), session_id, cwd)
        except AdwError as error:
            if error.kind == "authority_required":
                return False
            raise
        request_claim = request["claim"]
        claim = {
            "work_item": request_claim["work_item"], "decision": "specification_approved",
            "revision": request_claim["revision"], "role": request_claim["role"],
        }
        existing = find_specification_approval_receipt(
            receipt_root(), claim["work_item"], claim["revision"], claim["role"],
        )
        receipt = existing or create_receipt(
            receipt_root(), "human_approval", claim["role"], claim,
            canonical_json({
                "approval_request_ref": request["ref"], "human_message": prompt,
                "normalized_claim": claim,
            }),
            session_id, turn_id, event_id, cwd,
        )
        declaration_approved = approve_workflow_declaration(payload, request, receipt)
        emit({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": (
                    "Workflow approval captured for %s revision %s: %s (%s). %s"
                    % (
                        claim["work_item"], claim["revision"], receipt["ref"], receipt["artifact_sha256"],
                        "The matching workflow declaration is authorized."
                        if declaration_approved else
                        "No matching workflow declaration was changed.",
                    )
                ),
            }
        })
        return True
    return False


def extract_command(payload):
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command") or tool_input.get("cmd")
        if isinstance(command, str):
            return command, tool_input.get("workdir")
        source = tool_input.get("arguments")
    elif isinstance(tool_input, str):
        source = tool_input
    else:
        source = payload.get("arguments")
    if not isinstance(source, str):
        return None, None
    try:
        decoded = json.loads(source, object_pairs_hook=strict_object)
    except (ValueError, json.JSONDecodeError):
        decoded = None
    if isinstance(decoded, dict):
        command = decoded.get("command") or decoded.get("cmd")
        if isinstance(command, str):
            return command, decoded.get("workdir")
    source = source.lstrip()
    if source.startswith("// @exec:") and "\n" in source:
        source = source.split("\n", 1)[1].lstrip()
    call = re.match(
        r"(?:const\s+[A-Za-z_$][A-Za-z0-9_$]*\s*=\s*)?await\s+tools\.exec_command\(\s*",
        source,
    )
    if call is None:
        return None, None
    decoder = json.JSONDecoder(object_pairs_hook=strict_object)
    candidate = source[call.end():]
    try:
        arguments, end = decoder.raw_decode(candidate)
    except (ValueError, json.JSONDecodeError):
        return None, None
    if not candidate[end:].lstrip().startswith(")") or not isinstance(arguments, dict):
        return None, None
    command = arguments.get("command") or arguments.get("cmd")
    return (command, arguments.get("workdir")) if isinstance(command, str) else (None, None)


def find_flag(argv, name):
    try:
        index = argv.index(name)
    except ValueError:
        return None
    return argv[index + 1] if index + 1 < len(argv) else None


def read_proposal(path):
    candidate = Path(path)
    if not candidate.is_absolute() or candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_size > 65536:
        raise ValueError("workflow evidence proposal path is unsafe")
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise ValueError("workflow evidence proposal is not strict JSON")
    if not isinstance(value, dict):
        raise ValueError("workflow evidence proposal must be an object")
    return value


def capture_lead_call(payload):
    command, command_cwd = extract_command(payload)
    if command is None:
        return False
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    script_index = None
    if tokens and Path(tokens[0]).name == "adw.py":
        script_index = 0
    elif len(tokens) > 1 and Path(tokens[0]).name.startswith("python") and Path(tokens[1]).name == "adw.py":
        script_index = 1
    if script_index is None or script_index + 1 >= len(tokens):
        return False
    subcommand = tokens[script_index + 1]
    if subcommand not in {"prepare-approval", "record-approval", "record-evidence", "record-lead-decision", "run-evidence-command", "route-correction", "transition"}:
        return False
    host_cwd = Path(payload.get("cwd") or os.getcwd())
    cwd = Path(command_cwd) if isinstance(command_cwd, str) and command_cwd else host_cwd
    if not cwd.is_absolute():
        cwd = host_cwd / cwd
    cwd = cwd.resolve()
    script = Path(tokens[script_index])
    if not script.is_absolute():
        script = cwd / script
    normalized_argv = [str(script.resolve())] + tokens[script_index + 1:]
    work_item = tokens[script_index + 2] if script_index + 2 < len(tokens) else None
    claim = {
        "work_item": work_item,
        "argv_sha256": "sha256:" + hashlib.sha256(canonical_json(normalized_argv)).hexdigest(),
        "command_cwd": str(cwd),
        "subcommand": subcommand,
    }
    artifact = canonical_json(claim)
    if subcommand == "record-evidence":
        proposal_path = find_flag(tokens, "--record-file")
        if proposal_path is None:
            raise ValueError("record-evidence requires --record-file")
        proposal = read_proposal(proposal_path)
        claim["work_item"] = proposal.get("work_item")
        claim["proposal_sha256"] = "sha256:" + hashlib.sha256(canonical_json(proposal)).hexdigest()
        artifact = canonical_json(proposal)
    session_id, turn_id, event_id, hook_cwd = host_fields(payload)
    receipt = create_receipt(
        receipt_root(), "lead_call", "lead_agent", claim, artifact,
        session_id, turn_id, event_id, hook_cwd,
    )
    request_receipt = None
    if subcommand == "prepare-approval":
        delivery_root = find_flag(tokens, "--delivery-root")
        role = find_flag(tokens, "--role")
        expected_sequence = find_flag(tokens, "--expected-sequence")
        expected_head = find_flag(tokens, "--expected-head")
        try:
            expected_sequence = int(expected_sequence)
        except (TypeError, ValueError):
            raise ValueError("prepare-approval expected sequence is invalid")
        if not all(isinstance(value, str) and value for value in (delivery_root, role, expected_head)):
            raise ValueError("prepare-approval arguments are incomplete")
        request_receipt = create_specification_approval_request(
            resolve_work_item(delivery_root, work_item), role, receipt_root(),
            expected_sequence, expected_head, session_id, turn_id, event_id, hook_cwd,
        )
        bind_workflow_declaration(payload, request_receipt)
    emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "Workflow approval preflight captured: %s and %s" % (
                    receipt["ref"], request_receipt["ref"],
                ) if request_receipt else
                "Workflow lead-call receipt captured: %s" % receipt["ref"]
            ),
        }
    })
    return True


def capture_judge(payload):
    message = payload.get("last_assistant_message")
    prefix = "WORKFLOW_JUDGE_RESULT "
    if not isinstance(message, str) or not message.startswith(prefix):
        return False
    try:
        claim = json.loads(message[len(prefix):], object_pairs_hook=strict_object)
    except (ValueError, json.JSONDecodeError):
        raise ValueError("workflow judge result must contain strict JSON")
    expected = {"work_item", "decision", "state", "result_status", "supports", "input_revisions", "findings"}
    finding_fields = {"id", "severity", "classification", "blocking", "location", "criterion", "evidence", "status"}
    if (
        not isinstance(claim, dict) or set(claim) != expected
        or claim.get("result_status") != "pass" or not isinstance(claim.get("supports"), list)
        or any(not isinstance(value, str) or not value for value in claim["supports"])
        or not isinstance(claim.get("input_revisions"), dict)
        or any(not isinstance(key, str) or not isinstance(value, str) or not value for key, value in claim["input_revisions"].items())
        or not isinstance(claim.get("findings"), list)
        or any(
            not isinstance(finding, dict) or set(finding) != finding_fields
            or finding.get("severity") not in {"critical", "high", "medium", "low"}
            or not isinstance(finding.get("blocking"), bool)
            or any(not isinstance(finding.get(field), str) or not finding[field] for field in finding_fields - {"blocking", "severity"})
            for finding in claim["findings"]
        )
    ):
        raise ValueError("workflow judge result fields are invalid")
    session_id, turn_id, event_id, cwd = host_fields(payload)
    receipt = create_receipt(
        receipt_root(), "judge_output", "judge_agent", claim, canonical_json(claim),
        session_id, turn_id, event_id, cwd,
    )
    emit({"systemMessage": "Workflow judge receipt captured: %s (%s)" % (receipt["ref"], receipt["artifact_sha256"])})
    return True


def main():
    payload = read_input()
    if payload is None:
        emit({})
        return 0
    event = payload.get("hook_event_name")
    try:
        handled = (
            capture_human(payload) if event == "UserPromptSubmit" else
            capture_lead_call(payload) if event == "PreToolUse" else
            capture_judge(payload) if event == "SubagentStop" else
            False
        )
    except (ValueError, AdwError) as error:
        block(event, str(error))
        return 0
    if not handled:
        emit({})
    return 0


if __name__ == "__main__":
    sys.exit(main())
