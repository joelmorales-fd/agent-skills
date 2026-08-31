#!/usr/bin/env python3
"""Thin local command adapter for the Agentic Development Workflow."""

import argparse
import json
import sys
from pathlib import Path

from adw_core import AdwError, init_work_item, record_revision, record_specification_package, recover_work_item, resolve_work_item, route_correction, status_work_item, transition_work_item, validate_transition
from adw_receipts import default_receipt_root, find_lead_call_receipt, prepare_specification_approval, read_proposal_file, record_evidence_from_receipts, record_lead_gate_decision, record_specification_approval, run_evidence_command


def _parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="adw", parents=[common])
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", parents=[common])
    init.add_argument("ticket_id")
    init.add_argument("--repository", required=True)
    init.add_argument("--owner", required=True)
    init.add_argument("--delivery-root", required=True)
    init.add_argument("--request-id", required=True)
    init.add_argument("--lead-run-ref", required=True)
    status = commands.add_parser("status", parents=[common])
    status.add_argument("work_item")
    status.add_argument("--delivery-root", required=True)
    approval = commands.add_parser("prepare-approval", parents=[common])
    approval.add_argument("work_item")
    approval.add_argument("--delivery-root", required=True)
    approval.add_argument("--role", required=True, choices=("developer", "ticket_owner"))
    approval.add_argument("--expected-sequence", required=True, type=int)
    approval.add_argument("--expected-head", required=True)
    record_approval = commands.add_parser("record-approval", parents=[common])
    record_approval.add_argument("work_item")
    record_approval.add_argument("--delivery-root", required=True)
    record_approval.add_argument("--role", required=True, choices=("developer", "ticket_owner"))
    record_approval.add_argument("--expected-sequence", required=True, type=int)
    record_approval.add_argument("--expected-head", required=True)
    recover = commands.add_parser("recover", parents=[common])
    recover.add_argument("work_item")
    recover.add_argument("--delivery-root", required=True)
    recover.add_argument("--transaction", required=True)
    recover.add_argument("--request-id", required=True)
    recover.add_argument("--lead-run-ref", required=True)
    revision = commands.add_parser("record-revision", parents=[common])
    revision.add_argument("work_item")
    revision.add_argument("--delivery-root", required=True)
    revision.add_argument("--domain", required=True, choices=("test_design", "change", "configuration", "environment"))
    revision.add_argument("--source-ref", required=True)
    revision.add_argument("--fingerprint", required=True)
    revision.add_argument("--reason", required=True)
    revision.add_argument("--request-id", required=True)
    revision.add_argument("--expected-sequence", required=True, type=int)
    revision.add_argument("--expected-head", required=True)
    revision.add_argument("--lead-run-ref", required=True)
    specification = commands.add_parser("record-specification", parents=[common])
    specification.add_argument("work_item")
    specification.add_argument("--delivery-root", required=True)
    specification.add_argument("--reason", required=True)
    specification.add_argument("--request-id", required=True)
    specification.add_argument("--expected-sequence", required=True, type=int)
    specification.add_argument("--expected-head", required=True)
    specification.add_argument("--lead-run-ref", required=True)
    correction = commands.add_parser("route-correction", parents=[common])
    correction.add_argument("work_item")
    correction.add_argument("--delivery-root", required=True)
    correction.add_argument("--target-state", required=True, choices=("SPECIFY", "TEST_DESIGN", "TDD"))
    correction.add_argument("--reason", required=True)
    correction.add_argument("--next-action", required=True)
    correction.add_argument("--owner", required=True)
    correction.add_argument("--request-id", required=True)
    correction.add_argument("--expected-sequence", required=True, type=int)
    correction.add_argument("--expected-head", required=True)
    correction.add_argument("--lead-run-ref", required=True)
    lead_decision = commands.add_parser("record-lead-decision", parents=[common])
    lead_decision.add_argument("work_item")
    lead_decision.add_argument("--delivery-root", required=True)
    lead_decision.add_argument("--id", required=True)
    lead_decision.add_argument(
        "--gate", required=True,
        choices=("test_design_pass", "tdd_pass", "local_qa_pass", "mutation_decision"),
    )
    lead_decision.add_argument("--supports", action="append", default=[])
    lead_decision.add_argument("--historical-support", action="append", default=[])
    lead_decision.add_argument("--supersedes")
    lead_decision.add_argument("--expected-sequence", required=True, type=int)
    lead_decision.add_argument("--expected-head", required=True)
    record = commands.add_parser("record-evidence", parents=[common])
    record.add_argument("work_item")
    record.add_argument("--delivery-root", required=True)
    record.add_argument("--record-file", required=True)
    record.add_argument("--expected-sequence", required=True, type=int)
    record.add_argument("--expected-head", required=True)
    run = commands.add_parser("run-evidence-command", parents=[common])
    run.add_argument("work_item")
    run.add_argument("--delivery-root", required=True)
    run.add_argument("--id", required=True)
    run.add_argument("--cwd", required=True)
    run.add_argument("--source-ref", required=True)
    run.add_argument("--supports", action="append", default=[])
    run.add_argument("--expected-exit", action="append", type=int)
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument("--expected-sequence", required=True, type=int)
    run.add_argument("--expected-head", required=True)
    run.set_defaults(argv=[])
    validate = commands.add_parser("validate-transition", parents=[common])
    validate.add_argument("work_item")
    validate.add_argument("--delivery-root", required=True)
    validate.add_argument("--target-state", required=True)
    validate.add_argument("--decision-evidence", required=True)
    validate.add_argument("--resume-state")
    validate.add_argument("--resume-review-pass", choices=("first", "final"))
    validate.add_argument("--correction-attempt", action="append", default=[])
    transition = commands.add_parser("transition", parents=[common])
    transition.add_argument("work_item")
    transition.add_argument("--delivery-root", required=True)
    transition.add_argument("--validation-token", required=True)
    transition.add_argument("--reason", required=True)
    transition.add_argument("--next-action", required=True)
    transition.add_argument("--owner", required=True)
    transition.add_argument("--request-id", required=True)
    transition.add_argument("--expected-sequence", required=True, type=int)
    transition.add_argument("--expected-head", required=True)
    transition.add_argument("--lead-run-ref", required=True)
    return parser


def _emit_status(result):
    print("%s — Development Workflow" % result["work_item"])
    print("State: %s | Audit: %s" % (result["state"], result["audit_sequence"]))
    revisions = result.get("current_revisions", {})
    print("Revisions: %s" % ", ".join(
        "%s=%s" % (name, revisions.get(name) or "missing")
        for name in ("specification", "test_design", "change", "configuration", "environment")
    ))
    print("Progress:")
    revision = result.get("specification_revision")
    approval = result["gate_evidence"]["specification_approval"]
    if revision:
        print("  ✓ Specification package recorded (%s)" % revision)
    else:
        print("  → Specification package not recorded")
    if approval:
        print("  ✓ Human approval recorded (%s)" % approval)
    elif revision:
        print("  → Human approval not recorded")
    else:
        print("  · Human approval pending")
    stages = (
        ("test_design_pass", "Test design"), ("tdd_pass", "Implementation and tests"),
        ("first_review", "Code and test quality gate"), ("local_qa_pass", "Local QA verification"),
        ("mutation_decision", "Mutation gate"), ("final_review", "Delivery gate"),
    )
    current_gate = {
        "TEST_DESIGN": "test_design_pass", "TDD": "tdd_pass",
        "CODE_QUALITY_GATE": "first_review", "LOWER_ENV_VERIFY": "local_qa_pass",
        "MUTATION_GATE": "mutation_decision", "DELIVERY_GATE": "final_review",
    }.get(result["state"])
    for gate, label in stages:
        marker = "✓" if result["gate_evidence"][gate] else "→" if gate == current_gate else "·"
        print("  %s %s%s" % (marker, label, " complete" if marker == "✓" else " pending"))
    if result["state"] == "BLOCKED":
        print("  ! Blocked by: %s" % (", ".join(result["blocker_ids"]) or "unresolved blocker"))
    if result["state"] == "COMPLETE":
        print("  ✓ Workflow complete")
        print("Next: delivery handoff")
    elif result["state"] == "SPECIFY" and revision and not approval:
        print("Next: lead runs prepare-approval before asking the owner")
    elif result["state"] == "SPECIFY" and not revision:
        print("Next: complete and record the specification package")
    elif result["state"] == "SPECIFY":
        print("Next: record the approval evidence and transition to TEST_DESIGN")
    elif result["state"] == "BLOCKED":
        print("Next: resolve the named blocker, then resume from the recorded state")
    else:
        print("Next: satisfy the current %s exit gate" % result["state"])


def _emit_prepared_approval(result):
    print("%s — Specification Approval" % result["work_item"])
    print("  ✓ Receipt hook is active")
    print("  ✓ Immutable package: %s" % result["revision"])
    print("  Review: %s" % result["artifact_path"])
    if result["status"] == "approval_already_captured":
        print("  ✓ Human approval was already captured; do not ask again")
        print("Next: record the approval evidence")
    else:
        print("  → Waiting for the responsible owner")
        print("Reply: I approve")


def _emit(payload, output_format):
    if output_format == "json":
        print(json.dumps(payload, sort_keys=True))
        return
    if payload["ok"]:
        result = payload["result"]
        if payload["command"] == "status":
            _emit_status(result)
        elif payload["command"] == "prepare-approval":
            _emit_prepared_approval(result)
        else:
            print("%s: %s (%s)" % (payload["command"], result.get("work_item", result.get("work_item_path", result.get("transaction_id"))), result.get("state", result.get("status", "initialized"))))
    else:
        print("%s: %s" % (payload["error"]["kind"], payload["error"]["message"]), file=sys.stderr)


def main(argv=None, receipt_root=None):
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parse_argv = raw_argv
    command_argv = None
    if raw_argv[:1] == ["run-evidence-command"] and "--" in raw_argv:
        separator = raw_argv.index("--")
        parse_argv, command_argv = raw_argv[:separator], raw_argv[separator + 1:]
    arguments = _parser().parse_args(parse_argv)
    if command_argv is not None:
        arguments.argv = command_argv
    receipt_root = Path(receipt_root) if receipt_root is not None else default_receipt_root()
    try:
        if arguments.command == "init":
            result = init_work_item(
                arguments.ticket_id, arguments.repository, arguments.owner,
                arguments.delivery_root, arguments.request_id, arguments.lead_run_ref,
            )
            result["state"] = "SPECIFY"
        elif arguments.command == "status":
            result = status_work_item(arguments.work_item, arguments.delivery_root)
        elif arguments.command == "prepare-approval":
            try:
                lead = find_lead_call_receipt(
                    receipt_root, Path(__file__).resolve(), raw_argv, Path.cwd(), arguments.work_item,
                )
            except AdwError as error:
                if error.kind == "authority_required":
                    raise AdwError(
                        7, "authority_required",
                        "fresh workflow host receipt is missing; run prepare-approval alone in one tool call before asking the human",
                    )
                raise
            result = prepare_specification_approval(
                resolve_work_item(arguments.delivery_root, arguments.work_item), arguments.role,
                lead, receipt_root, arguments.expected_sequence, arguments.expected_head,
            )
        elif arguments.command == "record-approval":
            lead = find_lead_call_receipt(
                receipt_root, Path(__file__).resolve(), raw_argv, Path.cwd(), arguments.work_item,
            )
            result = record_specification_approval(
                resolve_work_item(arguments.delivery_root, arguments.work_item), arguments.role,
                lead, receipt_root, arguments.expected_sequence, arguments.expected_head,
            )
        elif arguments.command == "recover":
            result = recover_work_item(
                resolve_work_item(arguments.delivery_root, arguments.work_item),
                arguments.transaction, arguments.request_id, arguments.lead_run_ref,
            )
        elif arguments.command == "record-revision":
            result = record_revision(
                resolve_work_item(arguments.delivery_root, arguments.work_item), arguments.domain,
                arguments.source_ref, arguments.fingerprint, arguments.reason, arguments.request_id,
                arguments.expected_sequence, arguments.expected_head, arguments.lead_run_ref,
            )
        elif arguments.command == "record-specification":
            result = record_specification_package(
                resolve_work_item(arguments.delivery_root, arguments.work_item), arguments.reason,
                arguments.request_id, arguments.expected_sequence, arguments.expected_head,
                arguments.lead_run_ref,
            )
        elif arguments.command == "route-correction":
            lead = find_lead_call_receipt(
                receipt_root, Path(__file__).resolve(), raw_argv, Path.cwd(), arguments.work_item,
            )
            lead_run_ref = "codex:%s:%s:lead" % (lead["session_id"], lead["turn_id"])
            if arguments.lead_run_ref != lead_run_ref:
                raise AdwError(7, "authority_required", "route correction lead reference must match the host receipt")
            result = route_correction(
                resolve_work_item(arguments.delivery_root, arguments.work_item), arguments.target_state,
                arguments.reason, arguments.next_action, arguments.owner, arguments.request_id,
                arguments.expected_sequence, arguments.expected_head, lead_run_ref, lead["ref"],
            )
        elif arguments.command == "record-lead-decision":
            lead = find_lead_call_receipt(
                receipt_root, Path(__file__).resolve(), raw_argv, Path.cwd(), arguments.work_item,
            )
            result = record_lead_gate_decision(
                resolve_work_item(arguments.delivery_root, arguments.work_item), arguments.id,
                arguments.gate, arguments.supports, lead, arguments.expected_sequence,
                arguments.expected_head, historical_supports=arguments.historical_support,
                supersedes=arguments.supersedes,
            )
        elif arguments.command == "record-evidence":
            proposal = read_proposal_file(arguments.record_file)
            lead = find_lead_call_receipt(
                receipt_root, Path(__file__).resolve(), raw_argv, Path.cwd(), proposal.get("work_item"),
            )
            result = record_evidence_from_receipts(
                resolve_work_item(arguments.delivery_root, arguments.work_item), proposal,
                proposal.get("producer_proof_ref"), lead["ref"], receipt_root,
                arguments.expected_sequence, arguments.expected_head,
            )
        elif arguments.command == "run-evidence-command":
            lead = find_lead_call_receipt(
                receipt_root, Path(__file__).resolve(), raw_argv, Path.cwd(), arguments.work_item,
            )
            result = run_evidence_command(
                resolve_work_item(arguments.delivery_root, arguments.work_item), arguments.argv,
                arguments.cwd, arguments.id, arguments.source_ref, arguments.supports,
                arguments.expected_exit or [0], "codex:" + lead["event_id"],
                "codex:%s:%s:lead" % (lead["session_id"], lead["turn_id"]),
                arguments.expected_sequence, arguments.expected_head, arguments.timeout,
            )
        elif arguments.command == "validate-transition":
            result = validate_transition(
                resolve_work_item(arguments.delivery_root, arguments.work_item), arguments.target_state,
                None, arguments.decision_evidence, arguments.resume_state, arguments.resume_review_pass,
                arguments.correction_attempt,
            )
        else:
            lead = find_lead_call_receipt(
                receipt_root, Path(__file__).resolve(), raw_argv, Path.cwd(), arguments.work_item,
            )
            lead_run_ref = "codex:%s:%s:lead" % (lead["session_id"], lead["turn_id"])
            if arguments.lead_run_ref != lead_run_ref:
                raise AdwError(7, "authority_required", "transition lead reference must match the host receipt")
            try:
                token = json.loads(arguments.validation_token)
            except (TypeError, ValueError):
                raise AdwError(2, "invalid_input", "validation token must be strict JSON")
            result = transition_work_item(
                resolve_work_item(arguments.delivery_root, arguments.work_item), token, arguments.reason,
                arguments.next_action, arguments.owner, arguments.request_id, arguments.expected_sequence,
                arguments.expected_head, lead_run_ref,
            )
        _emit({"ok": True, "command": arguments.command, "result": result, "warnings": []}, arguments.format)
        return 0
    except AdwError as error:
        _emit({
            "ok": False, "command": arguments.command,
            "error": {"code": error.code, "kind": error.kind, "message": str(error), "details": []},
        }, arguments.format)
        return error.code
    except Exception:
        _emit({
            "ok": False, "command": arguments.command,
            "error": {"code": 10, "kind": "unexpected_error", "message": "unexpected local command failure", "details": []},
        }, arguments.format)
        return 10


if __name__ == "__main__":
    sys.exit(main())
