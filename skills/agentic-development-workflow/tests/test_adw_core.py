#!/usr/bin/env python3

import copy
import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from adw_core import AdwError, ControlBlock, InjectedCrash, LeaseLock, build_transaction, canonical_json, commit_transaction, init_work_item, read_consistent_snapshot, record_evidence, record_revision, recover_work_item, resolve_work_item, status_work_item, transition_work_item, validate_control_pair, validate_evidence_record, validate_root_cause_lineage, validate_transition, verify_artifact
import adw_core
import adw as adw_cli
import adw_receipts
from adw_receipts import cli_argv_sha256, create_receipt, create_specification_approval_request, find_current_approval_request, load_receipt, read_receipt_artifact, record_evidence_from_receipts, run_evidence_command


def valid_state():
    return {
        "work_item": "AVOD-1",
        "repository": "director2-aws",
        "state": "SPECIFY",
        "review_pass": None,
        "blocked_from_state": None,
        "blocked_from_review_pass": None,
        "resume_state": None,
        "resume_review_pass": None,
        "owner": "developer",
        "required_evidence_ids": [],
        "write_policy": {
            "policy_ref": "shared/local-write-policy",
            "policy_revision": "WRITE-1",
            "coordination_mode": "local_single_host",
            "lock_lease_seconds": 60,
            "transaction_schema": 1,
        },
        "audit": {
            "sequence": 1,
            "head": "sha256:" + "a" * 64,
            "last_transaction_id": "TX-1",
            "last_request_id": "REQUEST-1",
        },
        "current_revisions": {
            "specification": None,
            "test_design": None,
            "change": None,
            "configuration": None,
            "environment": None,
        },
        "revision_history": [],
        "gate_evidence": {
            "specification_approval": None,
            "test_design_pass": None,
            "tdd_pass": None,
            "first_review": None,
            "local_qa_pass": None,
            "mutation_decision": None,
            "final_review": None,
        },
        "transition_history": [],
        "loop_policy": {
            "policy_ref": "shared/loop-policy",
            "policy_revision": "LOOP-1",
            "max_attempts_per_root_cause": 3,
            "max_review_correction_loops": 5,
            "max_extension_units_per_decision": 1,
            "max_extension_decisions_per_scope": 1,
        },
        "blocker_ids": [],
        "exception_ids": [],
    }


def valid_evidence():
    return {
        "work_item": "AVOD-1",
        "audit": {
            "sequence": 1,
            "head": "sha256:" + "a" * 64,
            "last_transaction_id": "TX-1",
            "last_request_id": "REQUEST-1",
        },
        "evidence_index": [],
    }


def valid_support_record(evidence_id, artifact, state="SPECIFY", review_pass=None, result_status="pass", revisions=None, evidence_type="command_result", producer_role="qa_tool"):
    return {
        "id": evidence_id, "type": evidence_type, "work_item": "AVOD-1", "state": state, "review_pass": review_pass,
        "observed_at": "2026-01-01T00:00:00.000000Z", "recorded_at": "2026-01-01T00:00:00.000000Z",
        "result_status": result_status, "validity_status": "current", "producer_role": producer_role,
        "producer_ref": "producer/support", "producer_proof_ref": "receipt/support", "recorded_by": "lead/run-1",
        "source_ref": "support:%s" % evidence_id, "artifact_ref": "artifacts/evidence/%s.json" % evidence_id,
        "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(), "input_revisions": revisions or {},
        "supports": [], "historical_supports": [], "revision_transition": None, "supersedes": [], "invalidation_reason": None,
    }


def control_bytes(value, narrative=b"\n# Notes\n"):
    empty = ControlBlock.parse(b"---\n{}\n---\n" + narrative)
    return empty.replace(value)


def write_genesis(item, state=None, evidence=None):
    state = copy.deepcopy(state or valid_state())
    evidence = copy.deepcopy(evidence or valid_evidence())
    state["audit"]["head"] = None
    evidence["audit"]["head"] = None
    state_projection = copy.deepcopy(state)
    evidence_projection = copy.deepcopy(evidence)
    del state_projection["audit"]["head"]
    del evidence_projection["audit"]["head"]
    observed = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    runtime_configuration = canonical_json({
        "schema_version": 1, "profile": "director2-aws-local", "repository": "director2-aws",
        "delivery_root": str(item.parent), "template_source": "bundled", "template_fingerprints": {},
        "write_policy": state["write_policy"], "loop_policy": state["loop_policy"],
    })
    event = {
        "schema": 1,
        "work_item": "AVOD-1",
        "sequence": 1,
        "transaction_id": "TX-1",
        "request_id": "REQUEST-1",
        "command": "init",
        "safe_argument_hash": "sha256:" + hashlib.sha256(canonical_json({"command": "init", "safe_arguments": {}})).hexdigest(),
        "recorded_by": "lead/run-1",
        "started_at": observed,
        "prepared_at": observed,
        "previous_sequence": 0,
        "previous_head": None,
        "affected_control_blocks": ["evidence.md", "state.md"],
        "semantic_ids": [],
        "artifacts": [],
        "control_block_hashes": {
            "state.md": {"before": None, "after": "sha256:" + hashlib.sha256(canonical_json(state_projection)).hexdigest()},
            "evidence.md": {"before": None, "after": "sha256:" + hashlib.sha256(canonical_json(evidence_projection)).hexdigest()},
        },
        "narrative_hashes": {
            "state.md": {"before": None, "after": "sha256:" + hashlib.sha256(b"\n# State narrative\n").hexdigest()},
            "evidence.md": {"before": None, "after": "sha256:" + hashlib.sha256(b"\n# Evidence narrative\n").hexdigest()},
        },
        "intended_result": {
            "work_item": "AVOD-1",
            "runtime_configuration_sha256": "sha256:" + hashlib.sha256(runtime_configuration).hexdigest(),
        },
    }
    head = "sha256:" + hashlib.sha256(canonical_json(event)).hexdigest()
    for value in (state, evidence):
        value["audit"]["head"] = head
    state_bytes = control_bytes(state, b"\n# State narrative\n")
    evidence_bytes = control_bytes(evidence, b"\n# Evidence narrative\n")
    target_hashes = {
        "state.md": "sha256:" + hashlib.sha256(state_bytes).hexdigest(),
        "evidence.md": "sha256:" + hashlib.sha256(evidence_bytes).hexdigest(),
    }
    marker = {
        "schema": 1,
        "work_item": "AVOD-1",
        "sequence": 1,
        "transaction_id": "TX-1",
        "request_id": "REQUEST-1",
        "event_hash": head,
        "result_hash": "sha256:" + hashlib.sha256(canonical_json(event["intended_result"])).hexdigest(),
        "target_hashes": target_hashes,
        "artifact_hashes": {},
        "outcome": "committed",
        "commit_recorded_at": observed,
    }
    manifest = {
        "schema": 1,
        "work_item": "AVOD-1",
        "sequence": 1,
        "transaction_id": "TX-1",
        "request_id": "REQUEST-1",
        "command_input_hash": event["safe_argument_hash"],
        "event_hash": head,
        "expected_commit_marker_hash": "sha256:" + hashlib.sha256(canonical_json(marker)).hexdigest(),
        "targets": {
            name: {"before_hash": None, "staged_hash": digest}
            for name, digest in target_hashes.items()
        },
        "artifacts": {},
    }
    transaction = item / ".adw" / "transactions" / "1-TX-1"
    (transaction / "before").mkdir(parents=True)
    (transaction / "staged").mkdir()
    (transaction / "recovery-events").mkdir()
    (item / "artifacts").mkdir()
    (item / "state.md").write_bytes(state_bytes)
    (item / "evidence.md").write_bytes(evidence_bytes)
    (item / ".adw" / "runtime-configuration.json").write_bytes(runtime_configuration)
    (transaction / "staged" / "state.md").write_bytes(state_bytes)
    (transaction / "staged" / "evidence.md").write_bytes(evidence_bytes)
    (transaction / "audit-event.json").write_bytes(canonical_json(event))
    (transaction / "manifest.json").write_bytes(canonical_json(manifest))
    (transaction / "staged" / "commit-marker.json").write_bytes(canonical_json(marker))
    (transaction / "commit.json").write_bytes(canonical_json(marker))
    return state, evidence


def tree_file_bytes(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def open_fd_count():
    for path in (Path("/proc/self/fd"), Path("/dev/fd")):
        if path.is_dir():
            return len(list(path.iterdir()))
    raise unittest.SkipTest("open file-descriptor listing is unavailable")


class ControlBlockTests(unittest.TestCase):
    def test_parses_strict_json_and_preserves_narrative_bytes(self):
        raw = b'---\n{"audit":{"head":null,"sequence":0},"work_item":"AVOD-1"}\n---\n\n# Human notes\n\xff'

        document = ControlBlock.parse(raw)

        self.assertEqual("AVOD-1", document.value["work_item"])
        self.assertEqual(b"\n# Human notes\n\xff", document.narrative)
        self.assertEqual(document.narrative, document.replace(document.value).split(b"---\n", 2)[2])

    def test_replacement_rejects_non_canonical_floating_point_value(self):
        document = ControlBlock.parse(b'---\n{"work_item":"AVOD-1"}\n---\nnotes\n')

        with self.assertRaises(AdwError) as caught:
            document.replace({"ratio": 1.5})

        self.assertEqual(4, caught.exception.code)

    def test_replacement_converts_invalid_keys_and_unicode_to_code_four(self):
        document = ControlBlock.parse(b'---\n{"work_item":"AVOD-1"}\n---\nnotes\n')

        for invalid in ({1: "value"}, {"value": "\ud800"}):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(AdwError) as caught:
                    document.replace(invalid)
                self.assertEqual(4, caught.exception.code)

    def test_parser_rejects_invalid_unicode_and_normalized_duplicate_keys(self):
        invalid_documents = (
            b'---\n{"value":"\\ud800"}\n---\n',
            b'---\n{"e\\u0301":1,"\\u00e9":2}\n---\n',
        )

        for raw in invalid_documents:
            with self.subTest(raw=raw):
                with self.assertRaises(AdwError) as caught:
                    ControlBlock.parse(raw)
                self.assertEqual(4, caught.exception.code)


class CanonicalJsonTests(unittest.TestCase):
    def test_normalizes_strings_sorts_keys_and_ends_with_one_lf(self):
        value = {"z": "e\u0301", "a": [2, 1]}

        self.assertEqual(b'{"a":[2,1],"z":"\xc3\xa9"}\n', canonical_json(value))


class ControlSchemaTests(unittest.TestCase):
    def test_missing_field_is_invalid_control_block(self):
        state = valid_state()
        del state["loop_policy"]

        with self.assertRaises(AdwError) as caught:
            validate_control_pair(state, valid_evidence())

        self.assertEqual(4, caught.exception.code)

    def test_refine_cannot_fabricate_a_parent_edge(self):
        history = [
            {
                "type": "root_cause_record",
                "root_cause_relation": "new",
                "root_cause_ids": ["RC-1"],
                "parent_root_cause_ids": [],
            },
            {
                "type": "root_cause_record",
                "root_cause_relation": "refine",
                "root_cause_ids": ["RC-1"],
                "parent_root_cause_ids": ["RC-FAKE"],
            },
        ]

        with self.assertRaises(AdwError) as caught:
            validate_root_cause_lineage(history)

        self.assertEqual(4, caught.exception.code)

    def test_obsolete_review_pass_is_rejected(self):
        state = valid_state()
        state["review_pass"] = "first"

        with self.assertRaises(AdwError) as caught:
            validate_control_pair(state, valid_evidence())

        self.assertEqual(4, caught.exception.code)


class PathContainmentTests(unittest.TestCase):
    def test_rejects_path_outside_one_direct_ticket_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, "delivery")
            root.mkdir()
            outside = Path(temp, "outside")
            outside.mkdir()

            with self.assertRaises(AdwError) as caught:
                resolve_work_item(root, outside)

            self.assertEqual(2, caught.exception.code)


class InitAndStatusTests(unittest.TestCase):
    def test_initializes_an_absent_ticket_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            result = init_work_item(
                "AVOD-458-Testing", "director2-aws", "ticket-owner", delivery_root,
                "runtime-request-458", "runtime/lead-458",
                now=datetime(2026, 8, 30, tzinfo=timezone.utc),
            )

            item = Path(result["work_item_path"])
            self.assertTrue(all((item / name).is_file() for name in (
                "state.md", "01-scope.md", "02-investigation.md", "03-roadmap.md",
                "04-code-guide.md", "specification.md", "evidence.md", "review.md", "completion.md",
            )))
            self.assertFalse((item / "ticket.txt").exists())
            self.assertEqual("SPECIFY", status_work_item(item, delivery_root)["state"])

    def test_adopts_ticket_first_directory_without_changing_ticket_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-458-Testing"
            item.mkdir()
            ticket_bytes = b"Title: Support freeWithAds uxPromoTag for TV series\n"
            (item / "ticket.txt").write_bytes(ticket_bytes)

            result = init_work_item(
                "AVOD-458-Testing", "director2-aws", "ticket-owner", delivery_root,
                "runtime-request-458", "runtime/lead-458",
                now=datetime(2026, 8, 30, tzinfo=timezone.utc),
            )

            self.assertEqual(str(item.resolve()), result["work_item_path"])
            self.assertEqual(ticket_bytes, (item / "ticket.txt").read_bytes())
            self.assertTrue(all((item / name).is_file() for name in (
                "state.md", "01-scope.md", "02-investigation.md", "03-roadmap.md",
                "04-code-guide.md", "specification.md", "evidence.md", "review.md", "completion.md",
            )))
            self.assertTrue((item / "artifacts").is_dir())
            snapshot = read_consistent_snapshot(item)
            self.assertEqual("SPECIFY", snapshot.state["state"])
            self.assertEqual(1, snapshot.audit["sequence"])
            self.assertEqual("phase-1-local-1", snapshot.state["write_policy"]["policy_revision"])
            self.assertEqual("phase-1-local-1", snapshot.state["loop_policy"]["policy_revision"])
            self.assertNotIn("documentation/agentic", (item / "specification.md").read_text())
            self.assertTrue((item / ".adw" / "runtime-configuration.json").is_file())

            status = status_work_item(item, delivery_root)

            self.assertEqual({
                "work_item", "repository", "owner", "state", "review_pass", "audit_sequence",
                "audit_head", "transaction_id", "snapshot_token", "gate_evidence", "blocker_ids",
                "loop_policy_revision", "specification_revision", "current_revisions", "last_transition",
            }, set(status))
            self.assertNotIn("freeWithAds", json.dumps(status))

    def test_adopts_a_ticket_source_without_forcing_its_name_or_format(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-458"
            item.mkdir()
            source_name = "jira-export-AVOD-458.json"
            source_bytes = b'{"key":"AVOD-458","summary":"Jira is the source"}\n'
            (item / source_name).write_bytes(source_bytes)

            init_work_item(
                "AVOD-458", "director2-aws", "ticket-owner", delivery_root,
                "runtime-request-458", "runtime/lead-458",
                now=datetime(2026, 8, 30, tzinfo=timezone.utc),
            )

            self.assertEqual(source_bytes, (item / source_name).read_bytes())
            self.assertFalse((item / "ticket.txt").exists())
            self.assertEqual("SPECIFY", status_work_item(item, delivery_root)["state"])

    def test_rejects_partial_ticket_directory_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-458-Testing"
            item.mkdir()
            (item / "ticket.txt").write_bytes(b"ticket input")
            (item / "state.md").write_bytes(b"partial controlled record")
            before = tree_file_bytes(item)

            with self.assertRaises(AdwError) as caught:
                init_work_item(
                    "AVOD-458-Testing", "director2-aws", "ticket-owner", delivery_root,
                    "runtime-request-458", "runtime/lead-458",
                    now=datetime(2026, 8, 30, tzinfo=timezone.utc),
                )

            self.assertEqual(5, caught.exception.code)
            self.assertEqual(before, tree_file_bytes(item))

    def test_restores_ticket_first_directory_if_post_publish_ticket_check_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-458-Testing"
            item.mkdir()
            ticket_bytes = b"ticket input"
            (item / "ticket.txt").write_bytes(ticket_bytes)
            import adw_core
            original = adw_core._read_no_follow

            def alter_only_published_ticket(path):
                if Path(path).name == "ticket.txt" and (Path(path).parent / "state.md").exists():
                    return b"altered ticket bytes"
                return original(path)

            with mock.patch("adw_core._read_no_follow", side_effect=alter_only_published_ticket):
                with self.assertRaises(AdwError) as caught:
                    init_work_item(
                        "AVOD-458-Testing", "director2-aws", "ticket-owner", delivery_root,
                        "runtime-request-458", "runtime/lead-458",
                        now=datetime(2026, 8, 30, tzinfo=timezone.utc),
                    )

            self.assertEqual(8, caught.exception.code)
            self.assertEqual(ticket_bytes, (item / "ticket.txt").read_bytes())
            self.assertEqual(["ticket.txt"], [path.name for path in item.iterdir()])

    def test_rejects_relative_delivery_root(self):
        with self.assertRaises(AdwError) as caught:
            init_work_item(
                "AVOD-458-Testing", "director2-aws", "ticket-owner", Path("delivery"),
                "runtime-request-458", "runtime/lead-458",
                now=datetime(2026, 8, 30, tzinfo=timezone.utc),
            )

        self.assertEqual(2, caught.exception.code)

    def test_rejects_unsafe_ticket_id_without_creating_a_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            with self.assertRaises(AdwError) as caught:
                init_work_item(
                    "../escape", "director2-aws", "ticket-owner", delivery_root,
                    "runtime-request-458", "runtime/lead-458",
                    now=datetime(2026, 8, 30, tzinfo=timezone.utc),
                )

            self.assertEqual(2, caught.exception.code)
            self.assertEqual([], list(delivery_root.iterdir()))

    def test_rejects_invalid_generated_link_without_publishing_a_ticket(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            original = adw_core._read_no_follow

            def add_invalid_bundled_link(path):
                data = original(path)
                if Path(path).name == "specification.md" and Path(path).parent.name == "templates":
                    return data + b"\n[Invalid external dependency](../configuration/missing.md)\n"
                return data

            with mock.patch("adw_core._read_no_follow", side_effect=add_invalid_bundled_link):
                with self.assertRaises(AdwError) as caught:
                    init_work_item(
                        "AVOD-458-Testing", "director2-aws", "ticket-owner", delivery_root,
                        "runtime-request-458", "runtime/lead-458",
                        now=datetime(2026, 8, 30, tzinfo=timezone.utc),
                    )

            self.assertEqual(4, caught.exception.code)
            self.assertFalse((delivery_root / "AVOD-458-Testing").exists())
            self.assertFalse(any(path.name.startswith(".AVOD-458-Testing.init-") for path in delivery_root.iterdir()))

    def test_status_rejects_tampered_control_block(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-458-Testing"
            item.mkdir()
            (item / "ticket.txt").write_bytes(b"ticket input")
            init_work_item(
                "AVOD-458-Testing", "director2-aws", "ticket-owner", delivery_root,
                "runtime-request-458", "runtime/lead-458",
                now=datetime(2026, 8, 30, tzinfo=timezone.utc),
            )
            (item / "state.md").write_bytes(b"tampered")

            with self.assertRaises(AdwError) as caught:
                status_work_item(item, delivery_root)

            self.assertIn(caught.exception.code, {4, 8})

    def test_status_rejects_tampered_runtime_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            delivery_root = Path(temp) / "delivery"
            delivery_root.mkdir()
            result = init_work_item(
                "AVOD-458-Testing", "director2-aws", "ticket-owner", delivery_root,
                "runtime-request-458", "runtime/lead-458",
                now=datetime(2026, 8, 30, tzinfo=timezone.utc),
            )
            item = Path(result["work_item_path"])
            (item / ".adw" / "runtime-configuration.json").write_text("{}\n", encoding="utf-8")

            with self.assertRaises(AdwError) as caught:
                status_work_item(item, delivery_root)

            self.assertEqual(8, caught.exception.code)


class CliTests(unittest.TestCase):
    @staticmethod
    def write_specification_revision(item, state):
        artifact = b"# Immutable specification package\n"
        fingerprint = "sha256:" + hashlib.sha256(artifact).hexdigest()
        source_ref = "artifacts/specification-package-%s.md" % fingerprint.split(":", 1)[1]
        state["current_revisions"]["specification"] = "REV-SPEC"
        state["revision_history"].append({
            "id": "REV-SPEC", "domain": "specification", "source_ref": source_ref,
            "fingerprint": fingerprint, "reason": "Specification package complete",
            "recorded_at": "2026-01-02T00:00:00.000000Z", "recorder": "lead/run-1",
            "prior_revision": None,
        })
        return source_ref, artifact

    def test_route_correction_returns_to_specify_and_invalidates_old_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            delivery_root = Path(temp) / "delivery"
            receipt_root = Path(temp) / "receipts"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            source_ref, specification = self.write_specification_revision(item, state)
            state["state"] = "TEST_DESIGN"
            state["gate_evidence"]["specification_approval"] = "E-APPROVAL"
            approval_artifact = canonical_json({"decision": "specification_approved"})
            approval = valid_support_record(
                "E-APPROVAL", approval_artifact, revisions={"specification": "REV-SPEC"},
                evidence_type="approval_decision", producer_role="ticket_owner",
            )
            approval.update({
                "decision": "specification_approved", "gate": "specification_approval",
                "producer_proof_ref": "receipt:human-approval-1",
            })
            evidence["evidence_index"] = [approval]
            state, _ = write_genesis(item, state=state, evidence=evidence)
            (item / source_ref).write_bytes(specification)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-APPROVAL.json").write_bytes(approval_artifact)
            argv = [
                "route-correction", "AVOD-1", "--delivery-root", str(delivery_root),
                "--target-state", "SPECIFY", "--reason", "Investigation changed the specification",
                "--next-action", "Record the corrected specification package", "--owner", "developer",
                "--request-id", "REQUEST-CORRECTION-1", "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--lead-run-ref", "codex:session-route:turn-route:lead",
                "--format", "json",
            ]
            create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), argv),
                    "subcommand": "route-correction",
                },
                canonical_json({"work_item": "AVOD-1", "subcommand": "route-correction"}),
                "session-route", "turn-route", "event-route", str(Path.cwd()),
            )

            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = adw_cli.main(argv, receipt_root=receipt_root)

            self.assertEqual(0, result, stderr.getvalue())
            payload = json.loads(stdout.getvalue())["result"]
            self.assertEqual("SPECIFY", payload["state"])
            self.assertEqual(2, payload["audit_sequence"])
            snapshot = read_consistent_snapshot(item)
            self.assertIsNone(snapshot.state["gate_evidence"]["specification_approval"])
            self.assertEqual("invalidated", snapshot.evidence["evidence_index"][0]["validity_status"])
            self.assertIn("return to SPECIFY", snapshot.evidence["evidence_index"][0]["invalidation_reason"])
            route = snapshot.evidence["evidence_index"][-1]
            self.assertEqual("return_to_specify", route["decision"])
            self.assertEqual("lead_agent", route["producer_role"])
            self.assertEqual(route["id"], snapshot.state["transition_history"][-1]["decision_evidence_id"])
            with self.assertRaises(AdwError):
                validate_transition(item, "TEST_DESIGN", None, "E-APPROVAL")

    def test_prepare_approval_fails_before_asking_human_without_live_hook(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            source_ref, artifact = self.write_specification_revision(item, state)
            state, _ = write_genesis(item, state=state)
            (item / source_ref).write_bytes(artifact)
            argv = [
                "prepare-approval", "AVOD-1", "--delivery-root", str(delivery_root),
                "--role", "ticket_owner", "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]

            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = adw_cli.main(argv, receipt_root=receipt_root)

            self.assertEqual(7, result)
            payload = json.loads(stdout.getvalue())
            self.assertEqual("authority_required", payload["error"]["kind"])
            self.assertIn("before asking", payload["error"]["message"])
            self.assertFalse((receipt_root / "records").exists())

            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), argv),
                    "subcommand": "prepare-approval",
                },
                canonical_json({"work_item": "AVOD-1", "subcommand": "prepare-approval"}),
                "session-lead", "turn-forged", "tool-forged", str(Path.cwd()),
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(7, result)
            self.assertIn("host approval-request receipt is missing", json.loads(stdout.getvalue())["error"]["message"])

    def test_pretool_hook_prepares_the_approval_that_the_cli_accepts(self):
        hook = Path(__file__).parents[3] / "hooks" / "codex-workflow-receipts.py"
        if not hook.is_file():
            self.skipTest("plugin hook is outside the temporary mutation fixture")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            source_ref, artifact = self.write_specification_revision(item, state)
            state, _ = write_genesis(item, state=state)
            (item / source_ref).write_bytes(artifact)
            argv = [
                "prepare-approval", "AVOD-1", "--delivery-root", str(delivery_root),
                "--role", "ticket_owner", "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]
            command = shlex.join([sys.executable, str(Path(adw_cli.__file__).resolve())] + argv)
            payload = {
                "hook_event_name": "PreToolUse", "session_id": "session-lead",
                "turn_id": "turn-prepare", "tool_use_id": "tool-prepare",
                "cwd": str(Path.cwd()), "tool_input": {"command": command},
            }
            environment = dict(os.environ, AGENTIC_WORKFLOW_RECEIPT_ROOT=str(receipt_root),
                               PLUGIN_ROOT=str(Path(__file__).parents[3]), PYTHONDONTWRITEBYTECODE="1")

            captured = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
            self.assertEqual(0, captured.returncode, captured.stderr)
            context = json.loads(captured.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Workflow approval preflight captured", context)

            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                prepared = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(0, prepared, stderr.getvalue())
            self.assertEqual("awaiting_human_approval", json.loads(stdout.getvalue())["result"]["status"])

    def test_pretool_hook_prepares_approval_from_code_mode_exec(self):
        hook = Path(__file__).parents[3] / "hooks" / "codex-workflow-receipts.py"
        if not hook.is_file():
            self.skipTest("plugin hook is outside the temporary mutation fixture")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            source_ref, artifact = self.write_specification_revision(item, state)
            state, _ = write_genesis(item, state=state)
            (item / source_ref).write_bytes(artifact)
            argv = [
                "prepare-approval", "AVOD-1", "--delivery-root", str(delivery_root),
                "--role", "ticket_owner", "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]
            command = shlex.join([sys.executable, str(Path(adw_cli.__file__).resolve())] + argv)
            source = "const r = await tools.exec_command(%s);\ntext(r.output);" % json.dumps({
                "cmd": command, "workdir": str(Path.cwd()),
            })
            payload = {
                "hook_event_name": "PreToolUse", "session_id": "session-code-mode",
                "turn_id": "turn-prepare", "tool_use_id": "tool-prepare",
                "cwd": "/workspace/session", "tool_name": "exec",
                "tool_input": {"arguments": source},
            }
            environment = dict(os.environ, AGENTIC_WORKFLOW_RECEIPT_ROOT=str(receipt_root),
                               PLUGIN_ROOT=str(Path(__file__).parents[3]), PYTHONDONTWRITEBYTECODE="1")

            captured = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
            self.assertEqual(0, captured.returncode, captured.stderr)
            context = json.loads(captured.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Workflow approval preflight captured", context)

            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                prepared = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(0, prepared, stderr.getvalue())
            self.assertEqual("awaiting_human_approval", json.loads(stdout.getvalue())["result"]["status"])

    def test_natural_approval_is_revision_bound_and_reused_after_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            source_ref, artifact = self.write_specification_revision(item, state)
            state, _ = write_genesis(item, state=state)
            (item / source_ref).write_bytes(artifact)
            argv = [
                "prepare-approval", "AVOD-1", "--delivery-root", str(delivery_root),
                "--role", "ticket_owner", "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), argv),
                    "subcommand": "prepare-approval",
                },
                canonical_json({"work_item": "AVOD-1", "subcommand": "prepare-approval"}),
                "session-lead", "turn-prepare", "tool-prepare", str(Path.cwd()),
            )
            create_specification_approval_request(
                item, "ticket_owner", receipt_root, 1, state["audit"]["head"],
                lead["session_id"], lead["turn_id"], lead["event_id"], lead["cwd"],
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                prepared = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(0, prepared, stderr.getvalue())
            result = json.loads(stdout.getvalue())["result"]
            self.assertEqual("awaiting_human_approval", result["status"])
            self.assertEqual("I approve", result["reply"])
            self.assertEqual("REV-SPEC", result["revision"])
            self.assertEqual(source_ref, result["artifact_ref"])
            self.assertTrue(result["approval_request_ref"].startswith("receipt:approval_request-"))

            hook = Path(__file__).parents[3] / "hooks" / "codex-workflow-receipts.py"
            payload = {
                "hook_event_name": "UserPromptSubmit", "session_id": "session-lead",
                "turn_id": "turn-human", "cwd": str(Path.cwd()), "prompt": "I approve",
            }
            environment = dict(os.environ, AGENTIC_WORKFLOW_RECEIPT_ROOT=str(receipt_root),
                               PLUGIN_ROOT=str(Path(__file__).parents[3]), PYTHONDONTWRITEBYTECODE="1")
            captured = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
            self.assertEqual(0, captured.returncode, captured.stderr)
            hook_result = json.loads(captured.stdout)
            self.assertIn("Workflow approval captured", hook_result["hookSpecificOutput"]["additionalContext"])
            approvals = list((receipt_root / "records").glob("human_approval-*.json"))
            self.assertEqual(1, len(approvals))
            approval = load_receipt(receipt_root, "receipt:" + approvals[0].stem)
            self.assertEqual({
                "work_item": "AVOD-1", "decision": "specification_approved",
                "revision": "REV-SPEC", "role": "ticket_owner",
            }, approval["claim"])
            artifact = json.loads(read_receipt_artifact(receipt_root, approval))
            self.assertEqual("I approve", artifact["human_message"])

            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), argv),
                    "subcommand": "prepare-approval",
                },
                canonical_json({"work_item": "AVOD-1", "subcommand": "prepare-approval"}),
                "session-after-restart", "turn-restart", "tool-restart", str(Path.cwd()),
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                reused = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(0, reused, stderr.getvalue())
            reused_result = json.loads(stdout.getvalue())["result"]
            self.assertEqual("approval_already_captured", reused_result["status"])
            self.assertEqual(approval["ref"], reused_result["human_approval_ref"])

    def test_workflow_approval_authorizes_only_its_bound_declaration_and_records_without_proposal(self):
        hook = Path(__file__).parents[3] / "hooks" / "codex-workflow-receipts.py"
        declaration_hook = Path(__file__).parents[3] / "hooks" / "check-declaration.sh"
        resolver = Path(__file__).parents[3] / "hooks" / "resolve-declaration-file.sh"
        if not hook.is_file():
            self.skipTest("plugin hook is outside the temporary mutation fixture")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tmp").mkdir()
            (root / "home" / ".claude").mkdir(parents=True)
            receipt_root = root / "receipts"
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            source_ref, artifact = self.write_specification_revision(item, state)
            state, _ = write_genesis(item, state=state)
            (item / source_ref).write_bytes(artifact)

            environment = dict(
                os.environ,
                AGENTIC_WORKFLOW_RECEIPT_ROOT=str(receipt_root),
                PLUGIN_ROOT=str(Path(__file__).parents[3]),
                PYTHONDONTWRITEBYTECODE="1",
                TMPDIR=str(root / "tmp"),
                DECLARATION_CLIENT="codex",
                DECLARATION_SESSION_ID="session-lead",
                DECLARATION_CWD=str(Path.cwd()),
                HOME=str(root / "home"),
            )
            declaration_path = Path(subprocess.check_output(
                ["bash", str(resolver)], text=True, env=environment,
            ).strip())
            declaration_path.write_text(json.dumps({
                "task": "Implement AVOD-1 after specification approval",
                "files_to_touch": [
                    str(item / "specification.md"),
                    "director2/src/Feature.java",
                    "director2/test/FeatureTest.xml",
                ],
                "approved": True,
            }))

            prepare_argv = [
                "prepare-approval", "AVOD-1", "--delivery-root", str(delivery_root),
                "--role", "ticket_owner", "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]
            prepare_command = shlex.join([sys.executable, str(Path(adw_cli.__file__).resolve())] + prepare_argv)
            prepare_payload = {
                "hook_event_name": "PreToolUse", "session_id": "session-lead",
                "turn_id": "turn-prepare", "tool_use_id": "tool-prepare",
                "cwd": str(Path.cwd()), "tool_input": {"command": prepare_command},
            }
            prepared_hook = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(prepare_payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
            self.assertEqual(0, prepared_hook.returncode, prepared_hook.stderr)
            prepared_output = json.loads(prepared_hook.stdout)
            self.assertNotEqual(
                "deny", prepared_output.get("hookSpecificOutput", {}).get("permissionDecision"),
                prepared_hook.stdout,
            )
            bound = json.loads(declaration_path.read_text())
            self.assertFalse(bound["approved"])
            self.assertEqual("agentic-development-workflow", bound["workflow_authorization"]["name"])
            self.assertEqual("AVOD-1", bound["workflow_authorization"]["work_item"])
            self.assertEqual("REV-SPEC", bound["workflow_authorization"]["specification_revision"])
            self.assertEqual(4, len(bound["files_to_touch"]))
            self.assertIn(str(item.resolve() / "artifacts" / "**"), bound["files_to_touch"])

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(0, adw_cli.main(prepare_argv, receipt_root=receipt_root))

            changed = copy.deepcopy(bound)
            changed["files_to_touch"].append("director2/src/Injected.java")
            declaration_path.write_text(json.dumps(changed))
            approval_payload = {
                "hook_event_name": "UserPromptSubmit", "session_id": "session-lead",
                "turn_id": "turn-human", "cwd": str(Path.cwd()), "prompt": "I approve",
            }
            rejected_hook = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(approval_payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
            self.assertEqual(0, rejected_hook.returncode, rejected_hook.stderr)
            self.assertFalse(json.loads(declaration_path.read_text())["approved"])

            declaration_path.write_text(json.dumps(bound))
            approval_payload["turn_id"] = "turn-human-retry"
            approved_hook = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(approval_payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
            self.assertEqual(0, approved_hook.returncode, approved_hook.stderr)
            approved = json.loads(declaration_path.read_text())
            self.assertTrue(approved["approved"])
            self.assertRegex(
                approved["workflow_authorization"]["human_approval_ref"],
                r"^receipt:human_approval-[0-9a-f]{24}$",
            )
            artifact_check = subprocess.run(
                ["bash", str(declaration_hook)],
                input=json.dumps({
                    "tool_input": {
                        "file_path": str(item / "artifacts" / "test-design" / "snapshot.md"),
                    },
                }),
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
            self.assertEqual(0, artifact_check.returncode, artifact_check.stderr)

            record_argv = [
                "record-approval", "AVOD-1", "--delivery-root", str(delivery_root),
                "--role", "ticket_owner", "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]
            record_command = shlex.join([sys.executable, str(Path(adw_cli.__file__).resolve())] + record_argv)
            record_payload = {
                "hook_event_name": "PreToolUse", "session_id": "session-lead",
                "turn_id": "turn-record", "tool_use_id": "tool-record",
                "cwd": str(Path.cwd()), "tool_input": {"command": record_command},
            }
            recorded_hook = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(record_payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
            self.assertEqual(0, recorded_hook.returncode, recorded_hook.stderr)

            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = adw_cli.main(record_argv, receipt_root=receipt_root)
            self.assertEqual(0, result, stderr.getvalue())
            evidence_id = json.loads(stdout.getvalue())["result"]["evidence_id"]
            snapshot = read_consistent_snapshot(item)
            self.assertEqual(evidence_id, snapshot.state["gate_evidence"]["specification_approval"])
            self.assertFalse((item / ".adw" / "proposals").exists())

    def test_structured_approval_does_not_authorize_an_unbound_declaration(self):
        hook = Path(__file__).parents[3] / "hooks" / "codex-workflow-receipts.py"
        resolver = Path(__file__).parents[3] / "hooks" / "resolve-declaration-file.sh"
        if not hook.is_file():
            self.skipTest("plugin hook is outside the temporary mutation fixture")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tmp").mkdir()
            environment = dict(
                os.environ,
                AGENTIC_WORKFLOW_RECEIPT_ROOT=str(root / "receipts"),
                PLUGIN_ROOT=str(Path(__file__).parents[3]),
                PYTHONDONTWRITEBYTECODE="1",
                TMPDIR=str(root / "tmp"),
                DECLARATION_CLIENT="codex",
                DECLARATION_SESSION_ID="session-human",
                DECLARATION_CWD=str(Path.cwd()),
            )
            declaration_path = Path(subprocess.check_output(
                ["bash", str(resolver)], text=True, env=environment,
            ).strip())
            original = {
                "task": "Unrelated guarded edit",
                "files_to_touch": ["src/Unrelated.java"],
                "approved": False,
            }
            declaration_path.write_text(json.dumps(original))
            payload = {
                "hook_event_name": "UserPromptSubmit", "session_id": "session-human",
                "turn_id": "turn-human", "cwd": str(Path.cwd()),
                "prompt": (
                    'WORKFLOW_APPROVAL {"work_item":"AVOD-1",'
                    '"decision":"specification_approved","revision":"REV-SPEC",'
                    '"role":"ticket_owner"}'
                ),
            }

            captured = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )

            self.assertEqual(0, captured.returncode, captured.stderr)
            self.assertEqual(original, json.loads(declaration_path.read_text()))

    def test_record_approval_requires_the_exact_lead_subcommand(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            source_ref, specification = self.write_specification_revision(item, state)
            state, _ = write_genesis(item, state=state)
            (item / source_ref).write_bytes(specification)
            claim = {
                "work_item": "AVOD-1", "decision": "specification_approved",
                "revision": "REV-SPEC", "role": "ticket_owner",
            }
            create_receipt(
                receipt_root, "human_approval", "ticket_owner", claim, canonical_json({
                    "approval_request_ref": "receipt:approval_request-1234567890abcdef12345678",
                    "human_message": "I approve", "normalized_claim": claim,
                }),
                "session-human", "turn-human", "turn-human", str(Path.cwd()),
            )
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "subcommand": "record-approval"},
                canonical_json({"work_item": "AVOD-1", "subcommand": "record-approval"}),
                "session-lead", "turn-lead", "tool-lead", str(Path.cwd()),
            )
            wrong_call = copy.deepcopy(lead)
            wrong_call["claim"]["subcommand"] = "record-evidence"

            with self.assertRaises(AdwError) as caught:
                adw_receipts.record_specification_approval(
                    item, "ticket_owner", wrong_call, receipt_root,
                    state["audit"]["sequence"], state["audit"]["head"],
                )

            self.assertEqual("authority_required", caught.exception.kind)
            self.assertIsNone(read_consistent_snapshot(item).state["gate_evidence"]["specification_approval"])

    def test_natural_approval_rejects_a_request_after_the_specification_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            source_ref, artifact = self.write_specification_revision(item, state)
            state, _ = write_genesis(item, state=state)
            (item / source_ref).write_bytes(artifact)
            argv = [
                "prepare-approval", "AVOD-1", "--delivery-root", str(delivery_root),
                "--role", "ticket_owner", "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), argv),
                    "subcommand": "prepare-approval",
                },
                canonical_json({"work_item": "AVOD-1", "subcommand": "prepare-approval"}),
                "session-lead", "turn-prepare", "tool-prepare", str(Path.cwd()),
            )
            create_specification_approval_request(
                item, "ticket_owner", receipt_root, 1, state["audit"]["head"],
                lead["session_id"], lead["turn_id"], lead["event_id"], lead["cwd"],
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(0, adw_cli.main(argv, receipt_root=receipt_root))

            RevisionTests.write_complete_specification_package(item)
            adw_core.record_specification_package(
                item, "Specification changed before approval", "REQUEST-2",
                state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
            )
            with self.assertRaises(AdwError):
                find_current_approval_request(receipt_root, "session-lead", str(Path.cwd()))
            hook = Path(__file__).parents[3] / "hooks" / "codex-workflow-receipts.py"
            if not hook.is_file():
                return
            payload = {
                "hook_event_name": "UserPromptSubmit", "session_id": "session-lead",
                "turn_id": "turn-human", "cwd": str(Path.cwd()), "prompt": "I approve",
            }
            environment = dict(os.environ, AGENTIC_WORKFLOW_RECEIPT_ROOT=str(receipt_root),
                               PLUGIN_ROOT=str(Path(__file__).parents[3]), PYTHONDONTWRITEBYTECODE="1")

            captured = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(payload), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )

            self.assertEqual(0, captured.returncode, captured.stderr)
            self.assertEqual({}, json.loads(captured.stdout))
            self.assertEqual([], list((receipt_root / "records").glob("human_approval-*.json")))

    def test_text_status_shows_honest_human_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            source_ref, artifact = self.write_specification_revision(item, state)
            write_genesis(item, state=state)
            (item / source_ref).write_bytes(artifact)
            stdout, stderr = io.StringIO(), io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = adw_cli.main([
                    "status", "AVOD-1", "--delivery-root", str(delivery_root), "--format", "text",
                ], receipt_root=root / "receipts")

            self.assertEqual(0, result, stderr.getvalue())
            screen = stdout.getvalue()
            self.assertIn("AVOD-1 — Development Workflow", screen)
            self.assertIn("Revisions: specification=REV-SPEC", screen)
            self.assertIn("✓ Specification package recorded", screen)
            self.assertIn("→ Human approval not recorded", screen)
            self.assertIn("Next: lead runs prepare-approval before asking the owner", screen)
            self.assertNotIn("status: AVOD-1 (SPECIFY)", screen)

    def test_public_run_evidence_command_requires_host_call_and_records_actual_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            repository = root / "director2-aws"
            repository.mkdir()
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            command_argv = [sys.executable, "-c", "print('public-real-output')"]
            contract = (
                "# Scenario Verification Contract\n\n"
                "```adw-command-registry\n"
                + json.dumps({"commands": {"public-real": {
                    "argv": command_argv, "expected_exit_codes": [0], "timeout_seconds": 600,
                }}}, separators=(",", ":"))
                + "\n```\n"
            ).encode("utf-8")
            source_ref = "artifacts/test-design/public-command-contract.md"
            (item / source_ref).parent.mkdir(parents=True)
            (item / source_ref).write_bytes(contract)
            record_revision(
                item, "test_design", source_ref, "sha256:" + hashlib.sha256(contract).hexdigest(),
                "Register the public command", "REQUEST-TEST-DESIGN", state["audit"]["sequence"],
                state["audit"]["head"], "lead/run-1",
            )
            state = read_consistent_snapshot(item).state
            argv = [
                "run-evidence-command", "AVOD-1", "--delivery-root", str(delivery_root),
                "--id", "E-REAL-COMMAND", "--cwd", str(repository),
                "--source-ref", "command:public-real", "--expected-sequence", str(state["audit"]["sequence"]),
                "--expected-head", state["audit"]["head"], "--format", "json", "--",
                *command_argv,
            ]
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                missing = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(7, missing)
            self.assertEqual("authority_required", json.loads(stdout.getvalue())["error"]["kind"])

            create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1", "argv_sha256": "sha256:" + "0" * 64,
                    "subcommand": "run-evidence-command",
                },
                canonical_json({"work_item": "AVOD-1", "subcommand": "run-evidence-command"}),
                "session-lead", "turn-wrong", "tool-wrong", str(Path.cwd()),
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                mismatch = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(7, mismatch)
            self.assertEqual("authority_required", json.loads(stdout.getvalue())["error"]["kind"])

            create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), argv),
                    "subcommand": "run-evidence-command",
                },
                canonical_json({"work_item": "AVOD-1", "subcommand": "run-evidence-command"}),
                "session-lead", "turn-lead", "tool-real-command", str(Path.cwd()),
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                completed = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(0, completed, stderr.getvalue())
            self.assertEqual("E-REAL-COMMAND", json.loads(stdout.getvalue())["result"]["evidence_id"])
            recorded = read_consistent_snapshot(item).evidence["evidence_index"][-1]
            artifact = json.loads((item / recorded["artifact_ref"]).read_text())
            self.assertEqual(0, artifact["exit_code"])
            self.assertIn("public-real-output", artifact["stdout"])

    def test_public_record_evidence_requires_and_consumes_host_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            delivery_root = root / "delivery"
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"]["specification"] = "REV-SPEC"
            support_artifact = b'{"specification":"REV-SPEC"}\n'
            evidence["evidence_index"] = [valid_support_record(
                "E-SPEC", support_artifact, revisions={"specification": "REV-SPEC"}, evidence_type="artifact_snapshot",
            )]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-SPEC.json").write_bytes(support_artifact)
            approval = {"work_item": "AVOD-1", "decision": "specification_approved", "revision": "REV-SPEC"}
            artifact = canonical_json({
                "approval_request_ref": "receipt:approval_request-1234567890abcdef12345678",
                "human_message": "I approve", "normalized_claim": approval,
            })
            producer = create_receipt(
                receipt_root, "human_approval", "ticket_owner", approval, artifact,
                "session-human", "turn-human", "turn-human", str(root),
            )
            proposal = {
                "id": "E-APPROVAL", "type": "approval_decision", "work_item": "AVOD-1", "state": "SPECIFY",
                "review_pass": None, "observed_at": "2026-01-02T00:00:00.000000Z", "result_status": "pass",
                "validity_status": "current", "producer_role": "ticket_owner",
                "producer_ref": "codex-local-human:session-human", "producer_proof_ref": producer["ref"],
                "source_ref": "approval:turn-human", "artifact_ref": "artifacts/evidence/E-APPROVAL.json",
                "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(),
                "input_revisions": {"specification": "REV-SPEC"}, "supports": ["E-SPEC"],
                "historical_supports": [], "revision_transition": None, "supersedes": [],
                "invalidation_reason": None, "gate": "specification_approval", "decision": "specification_approved",
            }
            proposal_path = root / "approval.json"
            proposal_path.write_text(json.dumps(proposal))
            argv = [
                "record-evidence", "AVOD-1", "--delivery-root", str(delivery_root),
                "--record-file", str(proposal_path), "--expected-sequence", "1",
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                missing = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(7, missing)
            self.assertEqual("authority_required", json.loads(stdout.getvalue())["error"]["kind"])

            create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "proposal_sha256": "sha256:" + hashlib.sha256(canonical_json(proposal)).hexdigest(),
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), argv),
                    "subcommand": "record-evidence",
                },
                canonical_json(proposal), "session-lead", "turn-lead", "tool-lead", str(Path.cwd()),
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                completed = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(0, completed, stderr.getvalue())
            self.assertEqual("E-APPROVAL", json.loads(stdout.getvalue())["result"]["evidence_id"])

    def test_init_then_status_json_uses_only_safe_snapshot_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-458-Testing"
            item.mkdir()
            (item / "ticket.txt").write_bytes(b"Title: Support freeWithAds uxPromoTag for TV series\n")
            command = [sys.executable, str(Path(__file__).parents[1] / "scripts" / "adw.py")]
            init = subprocess.run(command + [
                "init", "AVOD-458-Testing", "--repository", "director2-aws", "--owner", "ticket-owner",
                "--delivery-root", str(delivery_root),
                "--request-id", "runtime-request-458", "--lead-run-ref", "runtime/lead-458", "--format", "json",
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            self.assertEqual(0, init.returncode, init.stderr)
            self.assertEqual("SPECIFY", json.loads(init.stdout)["result"]["state"])
            status = subprocess.run(command + [
                "status", str(item), "--delivery-root", str(delivery_root), "--format", "json",
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            self.assertEqual(0, status.returncode, status.stderr)
            payload = json.loads(status.stdout)
            self.assertEqual("SPECIFY", payload["result"]["state"])
            self.assertNotIn("freeWithAds", status.stdout)

    def test_init_is_self_contained_and_generates_ticket_runtime_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            delivery_root = Path(temp) / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-458-Testing"
            item.mkdir()
            (item / "ticket.txt").write_bytes(b"Title: self-contained workflow initialization\n")
            command = [sys.executable, str(Path(__file__).parents[1] / "scripts" / "adw.py")]

            initialized = subprocess.run(command + [
                "init", "AVOD-458-Testing", "--repository", "director2-aws", "--owner", "ticket-owner",
                "--delivery-root", str(delivery_root),
                "--request-id", "runtime-request-self-contained", "--lead-run-ref", "runtime/lead-self-contained",
                "--format", "json",
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            self.assertEqual(0, initialized.returncode, initialized.stderr)
            self.assertEqual("SPECIFY", json.loads(initialized.stdout)["result"]["state"])
            runtime_configuration = json.loads((item / ".adw" / "runtime-configuration.json").read_text())
            self.assertEqual("director2-aws-local", runtime_configuration["profile"])
            self.assertEqual(str(delivery_root.resolve()), runtime_configuration["delivery_root"])
            self.assertEqual("bundled", runtime_configuration["template_source"])
            self.assertEqual(set(adw_core.WORK_ITEM_DOCUMENTS), set(runtime_configuration["template_fingerprints"]))
            bundled_templates = Path(__file__).parents[1] / "assets" / "templates"
            self.assertEqual({
                name: "sha256:" + hashlib.sha256((bundled_templates / name).read_bytes()).hexdigest()
                for name in adw_core.WORK_ITEM_DOCUMENTS
            }, runtime_configuration["template_fingerprints"])
            self.assertNotIn("documentation/agentic", json.dumps(runtime_configuration))
            self.assertTrue(all((item / name).is_file() for name in adw_core.WORK_ITEM_DOCUMENTS))
            generated_documents = b"".join((item / name).read_bytes() for name in adw_core.WORK_ITEM_DOCUMENTS)
            self.assertNotIn(b"../configuration/", generated_documents)

    def test_recover_command_returns_structured_terminal_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            proposed_state = copy.deepcopy(state)
            proposed_state["owner"] = "lead/run-2"
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            with self.assertRaises(InjectedCrash):
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2", command="record-revision",
                    safe_arguments={"domain": "change"}, lead_run_ref="lead/run-2",
                    semantic_ids=["CHANGE-2"], intended_result={"revision_id": "CHANGE-2"},
                    now=acquired, crash_at="after_replace:state.md",
                )
            command = [sys.executable, str(Path(__file__).parents[1] / "scripts" / "adw.py")]
            recovered = subprocess.run(command + [
                "recover", str(item), "--delivery-root", str(delivery_root),
                "--transaction", "TX-2", "--request-id", "runtime-recovery-2",
                "--lead-run-ref", "runtime/lead-recovery-2", "--format", "json",
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            self.assertEqual(0, recovered.returncode, recovered.stderr)
            payload = json.loads(recovered.stdout)
            self.assertEqual("recover", payload["command"])
            self.assertEqual("aborted", payload["result"]["status"])

    def test_record_revision_command_returns_generated_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            command = [sys.executable, str(Path(__file__).parents[1] / "scripts" / "adw.py")]
            completed = subprocess.run(command + [
                "record-revision", "AVOD-1", "--delivery-root", str(delivery_root), "--domain", "change",
                "--source-ref", "git:abc123", "--fingerprint", "sha256:" + "b" * 64,
                "--reason", "Add behavior", "--request-id", "REQUEST-2",
                "--expected-sequence", str(state["audit"]["sequence"]), "--expected-head", state["audit"]["head"],
                "--lead-run-ref", "lead/run-2", "--format", "json",
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["result"]["revision_id"].startswith("REV-"))

    def test_record_specification_command_snapshots_the_complete_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            RevisionTests.write_complete_specification_package(item)
            command = [sys.executable, str(Path(__file__).parents[1] / "scripts" / "adw.py")]
            completed = subprocess.run(command + [
                "record-specification", "AVOD-1", "--delivery-root", str(delivery_root),
                "--reason", "Complete AVOD-style specification package", "--request-id", "REQUEST-2",
                "--expected-sequence", str(state["audit"]["sequence"]), "--expected-head", state["audit"]["head"],
                "--lead-run-ref", "lead/run-2", "--format", "json",
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            self.assertEqual(0, completed.returncode, completed.stderr)
            result = json.loads(completed.stdout)["result"]
            self.assertTrue(result["revision_id"].startswith("REV-"))
            self.assertTrue((item / result["source_ref"]).is_file())

    def test_validate_and_transition_commands_move_an_approved_specification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery_root = root / "delivery"
            delivery_root.mkdir()
            item = delivery_root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"]["specification"] = "REV-SPEC"
            state["gate_evidence"]["specification_approval"] = "E-APPROVAL"
            artifact = b'{"approved":true}\n'
            support_artifact = b'{"snapshot":true}\n'
            evidence["evidence_index"] = [valid_support_record("E-SUPPORT", support_artifact, revisions={"specification": "REV-SPEC"}), {
                "id": "E-APPROVAL", "type": "approval_decision", "work_item": "AVOD-1", "state": "SPECIFY",
                "review_pass": None, "producer_role": "ticket_owner", "producer_ref": "human/user-1",
                "producer_proof_ref": "receipt/1", "recorded_by": "lead/run-1", "source_ref": "approval:1",
                "artifact_ref": "artifacts/evidence/E-APPROVAL.json", "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(),
                "input_revisions": {"specification": "REV-SPEC"}, "result_status": "pass", "validity_status": "current",
                "supports": ["E-SUPPORT"], "historical_supports": [], "supersedes": [], "gate": "specification_approval",
                "decision": "specification_approved",
            }]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-SUPPORT.json").write_bytes(support_artifact)
            (item / "artifacts" / "evidence" / "E-APPROVAL.json").write_bytes(artifact)
            command = [sys.executable, str(Path(__file__).parents[1] / "scripts" / "adw.py")]
            validated = subprocess.run(command + [
                "validate-transition", "AVOD-1", "--delivery-root", str(delivery_root), "--target-state", "TEST_DESIGN",
                "--decision-evidence", "E-APPROVAL", "--format", "json",
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(0, validated.returncode, validated.stderr)
            token = json.loads(validated.stdout)["result"]
            receipt_root = root / "receipts"
            move_argv = [
                "transition", "AVOD-1", "--delivery-root", str(delivery_root), "--validation-token", json.dumps(token, separators=(",", ":")),
                "--reason", "Specification approved", "--next-action", "Design tests", "--owner", "lead/run-1",
                "--request-id", "REQUEST-2", "--expected-sequence", "1", "--expected-head", state["audit"]["head"],
                "--lead-run-ref", "codex:session-transition:turn-transition:lead", "--format", "json",
            ]
            create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), move_argv),
                    "subcommand": "transition",
                },
                canonical_json({"work_item": "AVOD-1", "subcommand": "transition"}),
                "session-transition", "turn-transition", "event-transition", str(Path.cwd()),
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                moved = adw_cli.main(move_argv, receipt_root=receipt_root)

            self.assertEqual(0, moved, stderr.getvalue())
            self.assertEqual("TEST_DESIGN", json.loads(stdout.getvalue())["result"]["state"])


class LeaseLockTests(unittest.TestCase):
    def test_expiry_never_displaces_a_held_advisory_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw").mkdir(parents=True)
            acquired = datetime(2026, 1, 1, tzinfo=timezone.utc)
            owner = LeaseLock.acquire(
                item, "write", "AVOD-1", "TX-1", "REQUEST-1", 1,
                "sha256:" + "a" * 64, "lead/run-1", 60, now=acquired,
            )
            try:
                with self.assertRaises(AdwError) as caught:
                    LeaseLock.acquire(
                        item, "write", "AVOD-1", "TX-2", "REQUEST-2", 1,
                        "sha256:" + "a" * 64, "lead/run-2", 60,
                        now=acquired + timedelta(minutes=2),
                    )

                self.assertEqual(6, caught.exception.code)
            finally:
                owner.release()

    def test_expired_orphan_is_preserved_only_after_acquiring_unchanged_flock(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw").mkdir(parents=True)
            recovery_events = item / ".adw" / "transactions" / "2-TX-2" / "recovery-events"
            recovery_events.mkdir(parents=True)
            acquired = datetime(2026, 1, 1, tzinfo=timezone.utc)
            orphan = LeaseLock.acquire(
                item, "write", "AVOD-1", "TX-1", "REQUEST-1", 1,
                "sha256:" + "a" * 64, "lead/run-1", 60, now=acquired,
            )
            os.close(orphan.descriptor)
            orphan.released = True

            claim = LeaseLock.claim_expired(
                item, "write", recovery_events, now=acquired + timedelta(minutes=2),
            )
            try:
                self.assertFalse((item / ".adw" / "write.lock").exists())
                self.assertTrue((claim.path / "owner.json").is_file())
                self.assertEqual(orphan.metadata_hash, claim.metadata_hash)
            finally:
                claim.close()

    def test_canonical_but_incomplete_owner_metadata_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw").mkdir(parents=True)
            acquired = datetime(2026, 1, 1, tzinfo=timezone.utc)
            orphan = LeaseLock.acquire(
                item, "write", "AVOD-1", "TX-1", "REQUEST-1", 1,
                "sha256:" + "a" * 64, "lead/run-1", 60, now=acquired,
            )
            orphan.abandon()
            owner_path = item / ".adw" / "write.lock" / "owner.json"
            metadata = json.loads(owner_path.read_text())
            del metadata["work_item"]
            owner_path.write_bytes(canonical_json(metadata))

            with self.assertRaises(AdwError) as caught:
                LeaseLock.acquire(
                    item, "write", "AVOD-1", "TX-2", "REQUEST-2", 1,
                    "sha256:" + "a" * 64, "lead/run-2", 60,
                    now=acquired + timedelta(minutes=2),
                )

            self.assertEqual("integrity_hold", caught.exception.kind)

    def test_tampered_owner_release_preserves_files_but_drops_process_handle(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw").mkdir(parents=True)
            acquired = datetime(2026, 1, 1, tzinfo=timezone.utc)
            owner = LeaseLock.acquire(
                item, "write", "AVOD-1", "TX-1", "REQUEST-1", 1,
                "sha256:" + "a" * 64, "lead/run-1", 60, now=acquired,
            )
            owner_path = item / ".adw" / "write.lock" / "owner.json"
            metadata = json.loads(owner_path.read_text())
            metadata["lead_run_ref"] = "tampered/run"
            owner_path.write_bytes(canonical_json(metadata))

            with self.assertRaises(AdwError) as release_error:
                owner.release()
            self.assertEqual("integrity_hold", release_error.exception.kind)
            self.assertTrue(owner_path.is_file())

            with self.assertRaises(AdwError) as next_owner:
                LeaseLock.acquire(
                    item, "write", "AVOD-1", "TX-2", "REQUEST-2", 1,
                    "sha256:" + "a" * 64, "lead/run-2", 60,
                    now=acquired + timedelta(minutes=2),
                )
            self.assertEqual("recovery_required", next_owner.exception.kind)

    def test_lock_directory_symlink_is_an_integrity_hold(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = root / "AVOD-1"
            outside = root / "outside"
            (item / ".adw").mkdir(parents=True)
            (outside / ".adw").mkdir(parents=True)
            acquired = datetime(2026, 1, 1, tzinfo=timezone.utc)
            orphan = LeaseLock.acquire(
                outside, "write", "AVOD-1", "TX-1", "REQUEST-1", 1,
                "sha256:" + "a" * 64, "lead/run-1", 60, now=acquired,
            )
            orphan.abandon()
            (item / ".adw" / "write.lock").symlink_to(outside / ".adw" / "write.lock")

            with self.assertRaises(AdwError) as caught:
                LeaseLock.acquire(
                    item, "write", "AVOD-1", "TX-2", "REQUEST-2", 1,
                    "sha256:" + "a" * 64, "lead/run-2", 60, now=acquired,
                )

            self.assertEqual(8, caught.exception.code)
            self.assertEqual("integrity_hold", caught.exception.kind)

    def test_stale_claim_rejects_a_symlinked_work_item(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw").mkdir(parents=True)
            recovery_events = item / ".adw" / "transactions" / "2-TX-2" / "recovery-events"
            recovery_events.mkdir(parents=True)
            acquired = datetime(2026, 1, 1, tzinfo=timezone.utc)
            orphan = LeaseLock.acquire(
                item, "write", "AVOD-1", "TX-1", "REQUEST-1", 1,
                "sha256:" + "a" * 64, "lead/run-1", 60, now=acquired,
            )
            orphan.abandon()
            alias = Path(temp, "alias")
            alias.symlink_to(item, target_is_directory=True)

            with self.assertRaises(AdwError) as caught:
                LeaseLock.claim_expired(
                    alias, "write", recovery_events, now=acquired + timedelta(minutes=2),
                )

            self.assertEqual(2, caught.exception.code)


class TransactionBuildTests(unittest.TestCase):
    def test_builder_owns_audit_hashes_and_avoids_marker_cycles(self):
        state = valid_state()
        evidence = valid_evidence()
        proposed_state = copy.deepcopy(state)
        proposed_state["owner"] = "lead/run-2"
        proposed_evidence = copy.deepcopy(evidence)
        prepared_at = datetime(2026, 1, 2, tzinfo=timezone.utc)

        prepared = build_transaction(
            control_bytes(state, b"\n# State narrative\n"),
            control_bytes(evidence, b"\n# Evidence narrative\n"),
            proposed_state,
            proposed_evidence,
            transaction_id="TX-2",
            request_id="REQUEST-2",
            command="record-revision",
            safe_arguments={"domain": "change"},
            lead_run_ref="lead/run-2",
            semantic_ids=["CHANGE-2"],
            intended_result={"revision_id": "CHANGE-2"},
            started_at=prepared_at,
            prepared_at=prepared_at,
        )

        event_bytes = canonical_json(prepared.audit_event)
        expected_head = "sha256:" + hashlib.sha256(event_bytes).hexdigest()
        staged_state = ControlBlock.parse(prepared.staged["state.md"]).value
        staged_evidence = ControlBlock.parse(prepared.staged["evidence.md"]).value
        self.assertEqual(expected_head, staged_state["audit"]["head"])
        self.assertEqual(staged_state["audit"], staged_evidence["audit"])
        state_projection = copy.deepcopy(staged_state)
        del state_projection["audit"]["head"]
        self.assertEqual(
            "sha256:" + hashlib.sha256(canonical_json(state_projection)).hexdigest(),
            prepared.audit_event["control_block_hashes"]["state.md"]["after"],
        )
        self.assertNotIn("manifest_hash", prepared.commit_marker)
        self.assertNotIn("commit_marker_hash", prepared.commit_marker)
        self.assertEqual(
            "sha256:" + hashlib.sha256(canonical_json(prepared.commit_marker)).hexdigest(),
            prepared.manifest["expected_commit_marker_hash"],
        )

    def test_builder_rejects_malformed_collection_inputs_with_code_four(self):
        state = valid_state()
        evidence = valid_evidence()

        with self.assertRaises(AdwError) as caught:
            build_transaction(
                control_bytes(state), control_bytes(evidence),
                copy.deepcopy(state), copy.deepcopy(evidence),
                transaction_id="TX-2", request_id="REQUEST-2", command="record-evidence",
                safe_arguments={}, lead_run_ref="lead/run-2", semantic_ids=[],
                intended_result={}, started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                prepared_at=datetime(2026, 1, 2, tzinfo=timezone.utc), artifacts=[],
            )

        self.assertEqual(4, caught.exception.code)


class TransactionCommitTests(unittest.TestCase):
    def make_item(self, temp):
        item = Path(temp, "AVOD-1")
        (item / ".adw" / "transactions").mkdir(parents=True)
        state, evidence = write_genesis(item)
        proposed_state = copy.deepcopy(state)
        proposed_state["owner"] = "lead/run-2"
        return item, state, evidence, proposed_state

    def test_commit_rejects_a_base_without_a_complete_committed_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            (item / "artifacts").mkdir()
            state = valid_state()
            evidence = valid_evidence()
            (item / "state.md").write_bytes(control_bytes(state))
            (item / "evidence.md").write_bytes(control_bytes(evidence))
            proposed_state = copy.deepcopy(state)
            proposed_state["owner"] = "lead/run-2"

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head="sha256:" + "a" * 64,
                    transaction_id="TX-2", request_id="REQUEST-2",
                    command="record-revision", safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                )

            self.assertEqual(8, caught.exception.code)

    def test_commit_stages_journal_then_publishes_one_shared_audit_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            state_narrative = b"\n# State narrative\n"
            evidence_narrative = b"\n# Evidence narrative\n"

            result = commit_transaction(
                item,
                proposed_state,
                copy.deepcopy(evidence),
                expected_sequence=1,
                expected_head=state["audit"]["head"],
                transaction_id="TX-2",
                request_id="REQUEST-2",
                command="record-revision",
                safe_arguments={"domain": "change"},
                lead_run_ref="lead/run-2",
                semantic_ids=["CHANGE-2"],
                intended_result={"revision_id": "CHANGE-2"},
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

            current_state = ControlBlock.parse((item / "state.md").read_bytes())
            current_evidence = ControlBlock.parse((item / "evidence.md").read_bytes())
            transaction = item / ".adw" / "transactions" / "2-TX-2"
            self.assertEqual(2, result["audit"]["sequence"])
            self.assertEqual(current_state.value["audit"], current_evidence.value["audit"])
            self.assertEqual(state_narrative, current_state.narrative)
            self.assertEqual(evidence_narrative, current_evidence.narrative)
            self.assertTrue((transaction / "before" / "state.md").is_file())
            self.assertTrue((transaction / "staged" / "state.md").is_file())
            self.assertTrue((transaction / "audit-event.json").is_file())
            self.assertTrue((transaction / "manifest.json").is_file())
            self.assertTrue((transaction / "commit.json").is_file())
            self.assertFalse((item / ".adw" / "write.lock").exists())
            self.assertEqual(2, read_consistent_snapshot(item).audit["sequence"])

    def test_conflict_after_first_replace_rolls_back_without_overwriting_human_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            base_state = (item / "state.md").read_bytes()
            base_evidence = (item / "evidence.md").read_bytes()
            human_evidence = control_bytes(evidence, b"\n# Concurrent human edit\n")

            def edit_before_second_replace(step, name, work_item):
                if step == "before_replace" and name == "evidence.md":
                    (work_item / "evidence.md").write_bytes(human_evidence)

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item,
                    proposed_state,
                    copy.deepcopy(evidence),
                    expected_sequence=1,
                    expected_head=state["audit"]["head"],
                    transaction_id="TX-2",
                    request_id="REQUEST-2",
                    command="record-revision",
                    safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2",
                    semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                    step_hook=edit_before_second_replace,
                )

            transaction = item / ".adw" / "transactions" / "2-TX-2"
            self.assertEqual(5, caught.exception.code)
            self.assertEqual(base_state, (item / "state.md").read_bytes())
            self.assertEqual(human_evidence, (item / "evidence.md").read_bytes())
            self.assertTrue((transaction / "abort.json").is_file())
            self.assertFalse((transaction / "commit.json").exists())

    def test_committed_same_request_returns_original_result_before_stale_cas(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            arguments = dict(
                expected_sequence=1,
                expected_head=state["audit"]["head"],
                request_id="REQUEST-2",
                command="record-revision",
                safe_arguments={"domain": "change"},
                lead_run_ref="lead/run-2",
                semantic_ids=["CHANGE-2"],
                intended_result={"revision_id": "CHANGE-2"},
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            first = commit_transaction(
                item, proposed_state, copy.deepcopy(evidence), transaction_id="TX-2", **arguments,
            )

            retry = commit_transaction(
                item, proposed_state, copy.deepcopy(evidence), transaction_id="TX-RETRY", **arguments,
            )

            self.assertEqual(first, retry)
            self.assertEqual(
                ["1-TX-1", "2-TX-2"],
                sorted(path.name for path in (item / ".adw" / "transactions").iterdir()),
            )

    def test_same_request_with_different_input_is_an_idempotency_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            common = dict(
                expected_sequence=1, expected_head=state["audit"]["head"],
                request_id="REQUEST-2", command="record-revision",
                lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                intended_result={"revision_id": "CHANGE-2"},
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            commit_transaction(
                item, proposed_state, copy.deepcopy(evidence), transaction_id="TX-2",
                safe_arguments={"domain": "change"}, **common,
            )
            before = tree_file_bytes(item)

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence), transaction_id="TX-RETRY",
                    safe_arguments={"domain": "environment"}, **common,
                )

            self.assertEqual(7, caught.exception.code)
            self.assertEqual(before, tree_file_bytes(item))

    def test_idempotent_retry_rejects_a_semantically_tampered_commit_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            arguments = dict(
                expected_sequence=1, expected_head=state["audit"]["head"],
                request_id="REQUEST-2", command="record-revision",
                safe_arguments={"domain": "change"}, lead_run_ref="lead/run-2",
                semantic_ids=["CHANGE-2"], intended_result={"revision_id": "CHANGE-2"},
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            commit_transaction(
                item, proposed_state, copy.deepcopy(evidence), transaction_id="TX-2", **arguments,
            )
            transaction = item / ".adw" / "transactions" / "2-TX-2"
            marker_path = transaction / "commit.json"
            manifest_path = transaction / "manifest.json"
            marker = json.loads(marker_path.read_text())
            manifest = json.loads(manifest_path.read_text())
            marker["outcome"] = "aborted"
            marker_path.write_bytes(canonical_json(marker))
            manifest["expected_commit_marker_hash"] = "sha256:" + hashlib.sha256(canonical_json(marker)).hexdigest()
            manifest_path.write_bytes(canonical_json(manifest))

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence), transaction_id="TX-RETRY", **arguments,
                )

            self.assertEqual(8, caught.exception.code)
            self.assertEqual("integrity_hold", caught.exception.kind)

    def test_idempotent_retry_maps_a_commit_marker_symlink_to_integrity_hold(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            arguments = dict(
                expected_sequence=1, expected_head=state["audit"]["head"],
                request_id="REQUEST-2", command="record-revision",
                safe_arguments={"domain": "change"}, lead_run_ref="lead/run-2",
                semantic_ids=["CHANGE-2"], intended_result={"revision_id": "CHANGE-2"},
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            commit_transaction(
                item, proposed_state, copy.deepcopy(evidence), transaction_id="TX-2", **arguments,
            )
            marker_path = item / ".adw" / "transactions" / "2-TX-2" / "commit.json"
            outside = Path(temp, "outside-marker.json")
            outside.write_bytes(marker_path.read_bytes())
            marker_path.unlink()
            marker_path.symlink_to(outside)

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence), transaction_id="TX-RETRY", **arguments,
                )

            self.assertEqual(8, caught.exception.code)
            self.assertEqual("integrity_hold", caught.exception.kind)

    def test_prepared_request_distinguishes_same_input_from_conflict(self):
        for safe_arguments, expected_code, expected_kind in (
            ({"domain": "change"}, 8, "recovery_required"),
            ({"domain": "environment"}, 7, "idempotency_conflict"),
        ):
            with self.subTest(safe_arguments=safe_arguments), tempfile.TemporaryDirectory() as temp:
                item, state, evidence, proposed_state = self.make_item(temp)
                acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
                with self.assertRaises(InjectedCrash):
                    commit_transaction(
                        item, proposed_state, copy.deepcopy(evidence),
                        expected_sequence=1, expected_head=state["audit"]["head"],
                        transaction_id="TX-2", request_id="REQUEST-2",
                        command="record-revision", safe_arguments={"domain": "change"},
                        lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                        intended_result={"revision_id": "CHANGE-2"}, now=acquired,
                        crash_at="after_preparation",
                    )
                recovery_events = item / ".adw" / "transactions" / "2-TX-2" / "recovery-events"
                claim = LeaseLock.claim_expired(
                    item, "write", recovery_events, now=acquired + timedelta(minutes=2),
                )
                claim.close()

                with self.assertRaises(AdwError) as caught:
                    commit_transaction(
                        item, proposed_state, copy.deepcopy(evidence),
                        expected_sequence=1, expected_head=state["audit"]["head"],
                        transaction_id="TX-RETRY", request_id="REQUEST-2",
                        command="record-revision", safe_arguments=safe_arguments,
                        lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                        intended_result={"revision_id": "CHANGE-2"},
                        now=acquired + timedelta(minutes=2),
                    )

                self.assertEqual(expected_code, caught.exception.code)
                self.assertEqual(expected_kind, caught.exception.kind)

    def test_crash_after_one_replace_leaves_mixed_snapshot_unreadable(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)

            with self.assertRaises(InjectedCrash):
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2",
                    command="record-revision", safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                    crash_at="after_replace:state.md",
                )

            transaction = item / ".adw" / "transactions" / "2-TX-2"
            self.assertEqual(2, ControlBlock.parse((item / "state.md").read_bytes()).value["audit"]["sequence"])
            self.assertEqual(1, ControlBlock.parse((item / "evidence.md").read_bytes()).value["audit"]["sequence"])
            self.assertFalse((transaction / "commit.json").exists())
            self.assertFalse((transaction / "abort.json").exists())
            with self.assertRaises(AdwError) as caught:
                read_consistent_snapshot(item, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
            self.assertIn(caught.exception.code, {6, 8})

    def test_every_publication_crash_boundary_remains_unreadable_until_recovery(self):
        boundaries = (
            "after_preparation",
            "after_artifact:artifacts/proof.txt",
            "after_replace:state.md",
            "after_replace:evidence.md",
            "after_verification",
            "after_commit_marker",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temp:
                item, state, evidence, proposed_state = self.make_item(temp)
                with self.assertRaises(InjectedCrash):
                    commit_transaction(
                        item, proposed_state, copy.deepcopy(evidence),
                        expected_sequence=1, expected_head=state["audit"]["head"],
                        transaction_id="TX-2", request_id="REQUEST-2",
                        command="record-evidence", safe_arguments={"type": "command_result"},
                        lead_run_ref="lead/run-2", semantic_ids=["E-2"],
                        intended_result={"evidence_id": "E-2"},
                        artifacts={"artifacts/proof.txt": b"redacted proof"},
                        now=datetime(2026, 1, 2, tzinfo=timezone.utc), crash_at=boundary,
                    )

                transaction = item / ".adw" / "transactions" / "2-TX-2"
                self.assertEqual(boundary == "after_commit_marker", (transaction / "commit.json").exists())
                self.assertFalse((transaction / "abort.json").exists())
                with self.assertRaises(AdwError) as caught:
                    read_consistent_snapshot(item, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
                self.assertIn(caught.exception.code, {6, 8})

    def test_stale_expected_token_changes_no_workflow_file(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            before = tree_file_bytes(item)

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=0, expected_head="sha256:" + "0" * 64,
                    transaction_id="TX-STALE", request_id="REQUEST-STALE",
                    command="record-revision", safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                )

            self.assertEqual(5, caught.exception.code)
            self.assertEqual(before, tree_file_bytes(item))

    def test_transaction_id_cannot_escape_the_journal_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            before = tree_file_bytes(item)

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="../escape", request_id="REQUEST-2",
                    command="record-revision", safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                )

            self.assertEqual(2, caught.exception.code)
            self.assertEqual(before, tree_file_bytes(item))

    def test_commit_rejects_a_symlinked_work_item(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            alias = Path(temp, "alias")
            alias.symlink_to(item, target_is_directory=True)
            before = tree_file_bytes(item)

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    alias, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2",
                    command="record-revision", safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                )

            self.assertEqual(2, caught.exception.code)
            self.assertEqual(before, tree_file_bytes(item))

    def test_immutable_artifact_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            existing = item / "artifacts" / "proof.txt"
            existing.write_bytes(b"existing evidence")

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2",
                    command="record-evidence", safe_arguments={"type": "command_result"},
                    lead_run_ref="lead/run-2", semantic_ids=["E-2"],
                    intended_result={"evidence_id": "E-2"},
                    artifacts={"artifacts/proof.txt": b"new evidence"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                )

            self.assertEqual(8, caught.exception.code)
            self.assertEqual(b"existing evidence", existing.read_bytes())
            self.assertEqual(1, ControlBlock.parse((item / "state.md").read_bytes()).value["audit"]["sequence"])

    def test_failure_after_artifact_link_orphans_the_uncommitted_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            import adw_core
            original = adw_core._open_regular_at
            artifact_opens = 0

            def fail_after_link(directory, name):
                nonlocal artifact_opens
                if name == "proof.txt":
                    artifact_opens += 1
                    if artifact_opens == 2:
                        raise AdwError(8, "integrity_hold", "injected post-link verification failure")
                return original(directory, name)

            with mock.patch("adw_core._open_regular_at", side_effect=fail_after_link):
                with self.assertRaises(AdwError):
                    commit_transaction(
                        item, proposed_state, copy.deepcopy(evidence),
                        expected_sequence=1, expected_head=state["audit"]["head"],
                        transaction_id="TX-2", request_id="REQUEST-2",
                        command="record-evidence", safe_arguments={"type": "command_result"},
                        lead_run_ref="lead/run-2", semantic_ids=["E-2"],
                        intended_result={"evidence_id": "E-2"},
                        artifacts={"artifacts/proof.txt": b"redacted proof"},
                        now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                    )

            transaction = item / ".adw" / "transactions" / "2-TX-2"
            self.assertFalse((item / "artifacts" / "proof.txt").exists())
            self.assertEqual(
                [b"redacted proof"],
                [path.read_bytes() for path in (transaction / "orphaned-artifacts").iterdir()],
            )
            self.assertTrue((transaction / "abort.json").is_file())

    def test_nested_artifact_parent_symlink_cannot_escape_work_item(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            outside = Path(temp, "outside")
            (outside / "nested").mkdir(parents=True)
            (item / "artifacts" / "escape").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2",
                    command="record-evidence", safe_arguments={"type": "command_result"},
                    lead_run_ref="lead/run-2", semantic_ids=["E-2"],
                    intended_result={"evidence_id": "E-2"},
                    artifacts={"artifacts/escape/nested/proof.txt": b"must stay contained"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                )

            self.assertEqual(2, caught.exception.code)
            self.assertFalse((outside / "nested" / "proof.txt").exists())

    def test_artifact_parent_substitution_after_validation_cannot_escape_work_item(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            nested = item / "artifacts" / "level1" / "level2"
            nested.mkdir(parents=True)
            outside = Path(temp, "outside")
            (outside / "level1" / "level2").mkdir(parents=True)

            def substitute_parent(step, name, work_item):
                if step == "before_artifact_publish":
                    nested.rmdir()
                    nested.parent.rmdir()
                    nested.parent.symlink_to(outside / "level1", target_is_directory=True)

            descriptors_before = open_fd_count()
            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2",
                    command="record-evidence", safe_arguments={"type": "command_result"},
                    lead_run_ref="lead/run-2", semantic_ids=["E-2"],
                    intended_result={"evidence_id": "E-2"},
                    artifacts={"artifacts/level1/level2/proof.txt": b"must stay contained"},
                    now=datetime(2026, 1, 2, tzinfo=timezone.utc), step_hook=substitute_parent,
                )

            self.assertIn(caught.exception.code, {2, 8})
            self.assertFalse((outside / "level1" / "level2" / "proof.txt").exists())
            self.assertEqual(descriptors_before, open_fd_count())

    def test_lease_expiry_before_first_publication_aborts_without_target_change(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            times = iter((acquired, acquired + timedelta(minutes=2)))

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2",
                    command="record-revision", safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"},
                    clock=lambda: next(times),
                )

            transaction = item / ".adw" / "transactions" / "2-TX-2"
            self.assertEqual(6, caught.exception.code)
            self.assertEqual(1, ControlBlock.parse((item / "state.md").read_bytes()).value["audit"]["sequence"])
            self.assertTrue((transaction / "abort.json").is_file())

            recovery_event = next((transaction / "recovery-events").glob("abort-*.json"))
            recovery = json.loads(recovery_event.read_text())
            recovery["abort_hash"] = "sha256:" + "0" * 64
            recovery_event.write_bytes(canonical_json(recovery))
            with self.assertRaises(AdwError) as tampered:
                read_consistent_snapshot(item)
            self.assertEqual(8, tampered.exception.code)

    def test_reusing_an_aborted_transaction_id_fails_with_a_stable_error(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            times = iter((acquired, acquired + timedelta(minutes=2)))
            with self.assertRaises(AdwError):
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2",
                    command="record-revision", safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"}, clock=lambda: next(times),
                )

            with self.assertRaises(AdwError) as caught:
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-NEW",
                    command="record-revision", safe_arguments={"domain": "change"},
                    lead_run_ref="lead/run-2", semantic_ids=["CHANGE-2"],
                    intended_result={"revision_id": "CHANGE-2"}, now=acquired,
                )

            self.assertEqual(8, caught.exception.code)
            self.assertEqual("integrity_hold", caught.exception.kind)

    def test_two_writers_from_one_head_cannot_both_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            item, state, evidence, proposed_state = self.make_item(temp)
            prepared = threading.Event()
            finish = threading.Event()
            outcomes = []

            def pause_first(step, name, work_item):
                if step == "prepared":
                    prepared.set()
                    self.assertTrue(finish.wait(5))

            def first_writer():
                try:
                    result = commit_transaction(
                        item, proposed_state, copy.deepcopy(evidence),
                        expected_sequence=1, expected_head=state["audit"]["head"],
                        transaction_id="TX-2A", request_id="REQUEST-2A",
                        command="record-revision", safe_arguments={"domain": "change"},
                        lead_run_ref="lead/run-A", semantic_ids=["CHANGE-2"],
                        intended_result={"revision_id": "CHANGE-2"},
                        now=datetime(2026, 1, 2, tzinfo=timezone.utc), step_hook=pause_first,
                    )
                    outcomes.append(("first", result["status"]))
                except Exception as error:
                    outcomes.append(("first", getattr(error, "code", None)))

            thread = threading.Thread(target=first_writer)
            thread.start()
            self.assertTrue(prepared.wait(5))
            try:
                with self.assertRaises(AdwError) as caught:
                    commit_transaction(
                        item, proposed_state, copy.deepcopy(evidence),
                        expected_sequence=1, expected_head=state["audit"]["head"],
                        transaction_id="TX-2B", request_id="REQUEST-2B",
                        command="record-revision", safe_arguments={"domain": "change"},
                        lead_run_ref="lead/run-B", semantic_ids=["CHANGE-2"],
                        intended_result={"revision_id": "CHANGE-2"},
                        now=datetime(2026, 1, 2, tzinfo=timezone.utc),
                    )
                self.assertEqual(6, caught.exception.code)
            finally:
                finish.set()
                thread.join(5)

            self.assertEqual([("first", "committed")], outcomes)
            self.assertEqual(2, read_consistent_snapshot(item).audit["sequence"])


class ConsistentReadTests(unittest.TestCase):
    def test_reads_only_a_complete_hash_chained_committed_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)

            snapshot = read_consistent_snapshot(item)

            self.assertEqual(state["audit"], snapshot.audit)
            self.assertEqual("AVOD-1", snapshot.state["work_item"])
            self.assertEqual(evidence["evidence_index"], snapshot.evidence["evidence_index"])
            self.assertTrue(snapshot.token.startswith("sha256:"))

    def test_control_block_or_event_tampering_enters_integrity_hold(self):
        for target in ("state.md", ".adw/transactions/1-TX-1/audit-event.json"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                item = Path(temp, "AVOD-1")
                (item / ".adw" / "transactions").mkdir(parents=True)
                write_genesis(item)
                path = item / target
                path.write_bytes(path.read_bytes() + b"tampered")

                with self.assertRaises(AdwError) as caught:
                    read_consistent_snapshot(item)

                self.assertEqual(8, caught.exception.code)

    def test_terminal_marker_semantics_cannot_be_rewritten_with_matching_manifest_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            write_genesis(item)
            transaction = item / ".adw" / "transactions" / "1-TX-1"
            marker_path = transaction / "commit.json"
            manifest_path = transaction / "manifest.json"
            marker = json.loads(marker_path.read_text())
            manifest = json.loads(manifest_path.read_text())
            marker["outcome"] = "aborted"
            marker_path.write_bytes(canonical_json(marker))
            manifest["expected_commit_marker_hash"] = "sha256:" + hashlib.sha256(canonical_json(marker)).hexdigest()
            manifest_path.write_bytes(canonical_json(manifest))

            with self.assertRaises(AdwError) as caught:
                read_consistent_snapshot(item)

            self.assertEqual(8, caught.exception.code)

    def test_commit_record_time_must_match_the_prepared_event(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            write_genesis(item)
            transaction = item / ".adw" / "transactions" / "1-TX-1"
            marker_path = transaction / "commit.json"
            manifest_path = transaction / "manifest.json"
            marker = json.loads(marker_path.read_text())
            manifest = json.loads(manifest_path.read_text())
            marker["commit_recorded_at"] = "2026-01-02T00:00:00.000000Z"
            marker_path.write_bytes(canonical_json(marker))
            (transaction / "staged" / "commit-marker.json").write_bytes(canonical_json(marker))
            manifest["expected_commit_marker_hash"] = "sha256:" + hashlib.sha256(canonical_json(marker)).hexdigest()
            manifest_path.write_bytes(canonical_json(manifest))

            with self.assertRaises(AdwError) as caught:
                read_consistent_snapshot(item)

            self.assertEqual(8, caught.exception.code)

    def test_unknown_filesystem_capability_enters_integrity_hold(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            write_genesis(item)
            completed = subprocess.CompletedProcess(["/sbin/mount"], 0, stdout="remote on / (nfs)\n", stderr="")

            with mock.patch("adw_core.subprocess.run", return_value=completed):
                with self.assertRaises(AdwError) as caught:
                    read_consistent_snapshot(item)

            self.assertEqual(8, caught.exception.code)

    def test_artifact_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "delivery", "AVOD-1")
            artifacts = item / "artifacts"
            artifacts.mkdir(parents=True)
            outside = Path(temp, "outside.txt")
            outside.write_bytes(b"not workflow evidence")
            (artifacts / "escape.txt").symlink_to(outside)

            with self.assertRaises(AdwError) as caught:
                verify_artifact(item, "artifacts/escape.txt", "sha256:" + "0" * 64)

            self.assertEqual(2, caught.exception.code)


class EvidenceValidationTests(unittest.TestCase):
    @staticmethod
    def register_test_design_commands(item, state, commands):
        contract = (
            "# Scenario Verification Contract\n\n"
            "```adw-command-registry\n"
            + json.dumps({"commands": commands}, separators=(",", ":"))
            + "\n```\n"
        ).encode("utf-8")
        source_ref = "artifacts/test-design/command-registry.md"
        (item / source_ref).parent.mkdir(parents=True, exist_ok=True)
        (item / source_ref).write_bytes(contract)
        record_revision(
            item, "test_design", source_ref, "sha256:" + hashlib.sha256(contract).hexdigest(),
            "Register evidence commands", "REQUEST-TEST-DESIGN", state["audit"]["sequence"],
            state["audit"]["head"], "lead/run-1",
        )
        return read_consistent_snapshot(item)

    def test_lead_cannot_approve_a_judge_owned_quality_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "CODE_QUALITY_GATE"
            state["current_revisions"].update({
                "specification": "REV-SPEC", "test_design": "REV-TEST-DESIGN",
                "change": "REV-CHANGE", "configuration": "REV-CONFIGURATION",
            })
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "subcommand": "record-lead-decision"},
                canonical_json({"gate": "first_review"}),
                "session-lead", "turn-lead", "tool-lead", "/workspace",
            )

            with self.assertRaises(AdwError) as caught:
                adw_receipts.record_lead_gate_decision(
                    item, "E-CODE-QUALITY", "first_review", [], lead,
                    state["audit"]["sequence"], state["audit"]["head"],
                )

            self.assertEqual("invalid_input", caught.exception.kind)
            self.assertIsNone(read_consistent_snapshot(item).state["gate_evidence"]["first_review"])

    def test_lead_can_record_its_receipt_bound_test_design_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TEST_DESIGN"
            state["current_revisions"].update({
                "specification": "REV-SPEC",
                "test_design": "REV-TEST-DESIGN",
                "configuration": "REV-CONFIGURATION",
            })
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "subcommand": "record-lead-decision"},
                canonical_json({"gate": "test_design_pass"}),
                "session-lead", "turn-lead", "tool-lead", "/workspace",
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            wrong_call = copy.deepcopy(lead)
            wrong_call["claim"]["subcommand"] = "record-evidence"
            with self.assertRaises(AdwError) as caught:
                adw_receipts.record_lead_gate_decision(
                    item, "E-WRONG-CALL", "test_design_pass", [], wrong_call,
                    state["audit"]["sequence"], state["audit"]["head"],
                )
            self.assertEqual("authority_required", caught.exception.kind)

            result = adw_receipts.record_lead_gate_decision(
                item, "E-TEST-DESIGN-PASS", "test_design_pass", [], lead,
                state["audit"]["sequence"], state["audit"]["head"],
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

            self.assertEqual("E-TEST-DESIGN-PASS", result["evidence_id"])
            snapshot = read_consistent_snapshot(item)
            self.assertEqual("E-TEST-DESIGN-PASS", snapshot.state["gate_evidence"]["test_design_pass"])
            recorded = snapshot.evidence["evidence_index"][-1]
            self.assertEqual("lead_agent", recorded["producer_role"])
            self.assertEqual(lead["ref"], recorded["producer_proof_ref"])

    def test_tdd_lead_gate_requires_actual_red_before_green(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            state["current_revisions"].update({
                "specification": "REV-SPEC", "test_design": "REV-TEST-DESIGN",
                "change": "REV-CHANGE", "configuration": "REV-CONFIGURATION",
            })
            revisions = copy.deepcopy(state["current_revisions"])
            red_artifact = canonical_json({"exit_code": 1, "phase": "red"})
            green_artifact = canonical_json({"exit_code": 0, "phase": "green"})
            early_green_artifact = canonical_json({"exit_code": 0, "phase": "early-green"})
            red = valid_support_record("E-RED", red_artifact, state="TDD", result_status="fail", revisions=revisions)
            green = valid_support_record("E-GREEN", green_artifact, state="TDD", revisions=revisions)
            early_green = valid_support_record("E-EARLY-GREEN", early_green_artifact, state="TDD", revisions=revisions)
            red["observed_at"] = "2026-01-02T00:00:00.000000Z"
            green["observed_at"] = "2026-01-03T00:00:00.000000Z"
            early_green["observed_at"] = "2026-01-01T00:00:00.000000Z"
            evidence["evidence_index"] = [red, green, early_green]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-RED.json").write_bytes(red_artifact)
            (item / "artifacts" / "evidence" / "E-GREEN.json").write_bytes(green_artifact)
            (item / "artifacts" / "evidence" / "E-EARLY-GREEN.json").write_bytes(early_green_artifact)
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "subcommand": "record-lead-decision"},
                canonical_json({"gate": "tdd_pass"}),
                "session-lead", "turn-lead", "tool-lead", "/workspace",
                now=datetime(2026, 1, 4, tzinfo=timezone.utc),
            )

            with self.assertRaises(AdwError) as caught:
                adw_receipts.record_lead_gate_decision(
                    item, "E-TDD-MISSING-RED", "tdd_pass", ["E-GREEN"], lead,
                    state["audit"]["sequence"], state["audit"]["head"],
                )
            self.assertEqual("incomplete_evidence", caught.exception.kind)

            with self.assertRaises(AdwError) as caught:
                adw_receipts.record_lead_gate_decision(
                    item, "E-TDD-WRONG-ORDER", "tdd_pass", ["E-EARLY-GREEN"], lead,
                    state["audit"]["sequence"], state["audit"]["head"], historical_supports=["E-RED"],
                )
            self.assertEqual("incomplete_evidence", caught.exception.kind)
            self.assertIn("precede", str(caught.exception))

            result = adw_receipts.record_lead_gate_decision(
                item, "E-TDD-PASS", "tdd_pass", ["E-GREEN"], lead,
                state["audit"]["sequence"], state["audit"]["head"],
                historical_supports=["E-RED"], now=datetime(2026, 1, 4, tzinfo=timezone.utc),
            )

            self.assertEqual("E-TDD-PASS", result["evidence_id"])
            recorded = read_consistent_snapshot(item).evidence["evidence_index"][-1]
            self.assertEqual(["E-GREEN"], recorded["supports"])
            self.assertEqual(["E-RED"], recorded["historical_supports"])

            (item / "artifacts" / "evidence" / "E-RED.json").write_bytes(b'{"tampered":true}\n')
            with self.assertRaises(AdwError) as caught:
                validate_transition(item, "CODE_QUALITY_GATE", None, "E-TDD-PASS")
            self.assertEqual("invalid_transition", caught.exception.kind)
            self.assertIn("integrity", str(caught.exception))

    def test_tdd_gate_requires_green_evidence_bound_to_the_recorded_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            state["current_revisions"].update({
                "specification": "REV-SPEC", "test_design": "REV-TEST-DESIGN",
                "change": "REV-CHANGE", "configuration": "REV-CONFIGURATION",
            })
            bound_revisions = copy.deepcopy(state["current_revisions"])
            unbound_revisions = {key: value for key, value in bound_revisions.items() if key != "change"}
            red_artifact = canonical_json({"exit_code": 1, "phase": "red"})
            green_artifact = canonical_json({"exit_code": 0, "phase": "green"})
            red = valid_support_record("E-RED", red_artifact, state="TDD", result_status="fail", revisions=unbound_revisions)
            green = valid_support_record("E-GREEN", green_artifact, state="TDD", revisions=unbound_revisions)
            red["observed_at"] = "2026-01-02T00:00:00.000000Z"
            green["observed_at"] = "2026-01-03T00:00:00.000000Z"
            evidence["evidence_index"] = [red, green]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-RED.json").write_bytes(red_artifact)
            (item / "artifacts" / "evidence" / "E-GREEN.json").write_bytes(green_artifact)
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "subcommand": "record-lead-decision"},
                canonical_json({"gate": "tdd_pass"}),
                "session-lead", "turn-lead", "tool-lead", "/workspace",
            )

            with self.assertRaises(AdwError) as caught:
                adw_receipts.record_lead_gate_decision(
                    item, "E-TDD-PASS", "tdd_pass", ["E-GREEN"], lead,
                    state["audit"]["sequence"], state["audit"]["head"],
                    historical_supports=["E-RED"],
                )

            self.assertEqual("incomplete_evidence", caught.exception.kind)
            self.assertIn("change revision", str(caught.exception))

    def test_tdd_gate_requires_a_recorded_change_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            state["current_revisions"].update({
                "specification": "REV-SPEC", "test_design": "REV-TEST-DESIGN",
                "configuration": "REV-CONFIGURATION",
            })
            revisions = {key: value for key, value in state["current_revisions"].items() if key != "change"}
            red_artifact = canonical_json({"exit_code": 1, "phase": "red"})
            green_artifact = canonical_json({"exit_code": 0, "phase": "green"})
            red = valid_support_record("E-RED", red_artifact, state="TDD", result_status="fail", revisions=revisions)
            green = valid_support_record("E-GREEN", green_artifact, state="TDD", revisions=revisions)
            red["observed_at"] = "2026-01-02T00:00:00.000000Z"
            green["observed_at"] = "2026-01-03T00:00:00.000000Z"
            evidence["evidence_index"] = [red, green]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-RED.json").write_bytes(red_artifact)
            (item / "artifacts" / "evidence" / "E-GREEN.json").write_bytes(green_artifact)
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "subcommand": "record-lead-decision"},
                canonical_json({"gate": "tdd_pass"}),
                "session-lead", "turn-lead", "tool-lead", "/workspace",
            )

            with self.assertRaises(AdwError) as caught:
                adw_receipts.record_lead_gate_decision(
                    item, "E-TDD-PASS", "tdd_pass", ["E-GREEN"], lead,
                    state["audit"]["sequence"], state["audit"]["head"],
                    historical_supports=["E-RED"],
                )

            self.assertEqual("incomplete_evidence", caught.exception.kind)
            self.assertIn("recorded change revision", str(caught.exception))

    def test_tdd_gate_can_explicitly_supersede_a_stale_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            state["current_revisions"].update({
                "specification": "REV-SPEC", "test_design": "REV-TEST-DESIGN",
                "change": "REV-CHANGE", "configuration": "REV-CONFIGURATION",
            })
            revisions = copy.deepcopy(state["current_revisions"])
            red_artifact = canonical_json({"exit_code": 1, "phase": "red"})
            green_artifact = canonical_json({"exit_code": 0, "phase": "green"})
            red = valid_support_record("E-RED", red_artifact, state="TDD", result_status="fail", revisions=revisions)
            green = valid_support_record("E-GREEN", green_artifact, state="TDD", revisions=revisions)
            red["observed_at"] = "2026-01-02T00:00:00.000000Z"
            green["observed_at"] = "2026-01-03T00:00:00.000000Z"
            evidence["evidence_index"] = [red, green]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-RED.json").write_bytes(red_artifact)
            (item / "artifacts" / "evidence" / "E-GREEN.json").write_bytes(green_artifact)
            first_lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "subcommand": "record-lead-decision"},
                canonical_json({"gate": "tdd_pass"}),
                "session-lead", "turn-first", "tool-first", "/workspace",
            )
            adw_receipts.record_lead_gate_decision(
                item, "E-TDD-STALE", "tdd_pass", ["E-GREEN"], first_lead,
                state["audit"]["sequence"], state["audit"]["head"],
                historical_supports=["E-RED"],
            )
            snapshot = read_consistent_snapshot(item)
            replacement_lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "subcommand": "record-lead-decision"},
                canonical_json({"gate": "tdd_pass"}),
                "session-lead", "turn-replacement", "tool-replacement", "/workspace",
            )

            adw_receipts.record_lead_gate_decision(
                item, "E-TDD-CURRENT", "tdd_pass", ["E-GREEN"], replacement_lead,
                snapshot.audit["sequence"], snapshot.audit["head"],
                historical_supports=["E-RED"], supersedes="E-TDD-STALE",
            )

            snapshot = read_consistent_snapshot(item)
            self.assertEqual("E-TDD-CURRENT", snapshot.state["gate_evidence"]["tdd_pass"])
            records = {record["id"]: record for record in snapshot.evidence["evidence_index"]}
            self.assertEqual("superseded", records["E-TDD-STALE"]["validity_status"])
            self.assertEqual(["E-TDD-STALE"], records["E-TDD-CURRENT"]["supersedes"])

    def test_public_cli_records_a_host_bound_lead_gate_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TEST_DESIGN"
            state["current_revisions"].update({
                "specification": "REV-SPEC",
                "test_design": "REV-TEST-DESIGN",
                "configuration": "REV-CONFIGURATION",
            })
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            argv = [
                "record-lead-decision", "AVOD-1", "--delivery-root", str(root),
                "--id", "E-TEST-DESIGN-PASS", "--gate", "test_design_pass",
                "--expected-sequence", str(state["audit"]["sequence"]),
                "--expected-head", state["audit"]["head"], "--format", "json",
            ]
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                missing_receipt = adw_cli.main(argv, receipt_root=receipt_root)
            self.assertEqual(7, missing_receipt)
            self.assertIsNone(read_consistent_snapshot(item).state["gate_evidence"]["test_design_pass"])

            create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {
                    "work_item": "AVOD-1",
                    "argv_sha256": cli_argv_sha256(Path(adw_cli.__file__).resolve(), argv),
                    "command_cwd": str(Path.cwd()),
                    "subcommand": "record-lead-decision",
                },
                canonical_json({"gate": "test_design_pass"}),
                "session-lead", "turn-lead", "tool-lead", str(Path.cwd()),
            )

            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = adw_cli.main(argv, receipt_root=receipt_root)

            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("E-TEST-DESIGN-PASS", json.loads(stdout.getvalue())["result"]["evidence_id"])
            self.assertEqual(
                "E-TEST-DESIGN-PASS",
                read_consistent_snapshot(item).state["gate_evidence"]["test_design_pass"],
            )

    def test_host_receipt_round_trip_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, "receipts")
            artifact = canonical_json({"approved": True})
            receipt = create_receipt(
                root, "human_approval", "ticket_owner",
                {"work_item": "AVOD-1", "decision": "specification_approved", "revision": "REV-SPEC"},
                artifact, "session-1", "turn-1", "turn-1", "/workspace",
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

            loaded = load_receipt(root, receipt["ref"])
            self.assertEqual(receipt["id"], loaded["id"])
            self.assertEqual(artifact, read_receipt_artifact(root, loaded))
            path = root / "records" / (receipt["id"] + ".json")
            path.chmod(0o644)
            with self.assertRaises(AdwError) as caught:
                load_receipt(root, receipt["ref"])
            self.assertEqual("authority_required", caught.exception.kind)
            path.chmod(0o600)
            tampered = json.loads(path.read_text())
            tampered["claim"]["revision"] = "REV-OTHER"
            path.write_text(json.dumps(tampered))

            with self.assertRaises(AdwError) as caught:
                load_receipt(root, receipt["ref"])
            self.assertEqual("authority_required", caught.exception.kind)

    def test_receipt_verified_public_evidence_records_real_human_approval_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_root = root / "receipts"
            item = root / "AVOD-1"
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"]["specification"] = "REV-SPEC"
            snapshot_artifact = b'{"specification":"REV-SPEC"}\n'
            evidence["evidence_index"] = [valid_support_record(
                "E-SPEC", snapshot_artifact, revisions={"specification": "REV-SPEC"}, evidence_type="artifact_snapshot",
            )]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-SPEC.json").write_bytes(snapshot_artifact)
            approval_claim = {
                "work_item": "AVOD-1", "decision": "specification_approved", "revision": "REV-SPEC",
            }
            approval_artifact = canonical_json({
                "approval_request_ref": "receipt:approval_request-1234567890abcdef12345678",
                "human_message": "I approve", "normalized_claim": approval_claim,
            })
            producer = create_receipt(
                receipt_root, "human_approval", "ticket_owner",
                approval_claim,
                approval_artifact, "session-human", "turn-human", "turn-human", "/workspace",
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            proposal = {
                "id": "E-APPROVAL", "type": "approval_decision", "work_item": "AVOD-1", "state": "SPECIFY",
                "review_pass": None, "observed_at": "2026-01-02T00:00:00.000000Z", "result_status": "pass",
                "validity_status": "current", "producer_role": "ticket_owner", "producer_ref": "codex-local-human:session-human",
                "producer_proof_ref": producer["ref"], "source_ref": "approval:turn-human",
                "artifact_ref": "artifacts/evidence/E-APPROVAL.json",
                "integrity_ref": "sha256:" + hashlib.sha256(approval_artifact).hexdigest(),
                "input_revisions": {"specification": "REV-SPEC"}, "supports": ["E-SPEC"],
                "historical_supports": [], "revision_transition": None, "supersedes": [],
                "invalidation_reason": None, "gate": "specification_approval", "decision": "specification_approved",
            }
            lead = create_receipt(
                receipt_root, "lead_call", "lead_agent",
                {"work_item": "AVOD-1", "proposal_sha256": "sha256:" + hashlib.sha256(canonical_json(proposal)).hexdigest()},
                canonical_json(proposal), "session-lead", "turn-lead", "tool-1", "/workspace",
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

            result = record_evidence_from_receipts(
                item, proposal, producer["ref"], lead["ref"], receipt_root,
                state["audit"]["sequence"], state["audit"]["head"],
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            self.assertEqual("E-APPROVAL", result["evidence_id"])
            self.assertEqual("E-APPROVAL", read_consistent_snapshot(item).state["gate_evidence"]["specification_approval"])

            duplicate = copy.deepcopy(proposal)
            duplicate["id"] = "E-APPROVAL-REPLAY"
            current = read_consistent_snapshot(item)
            with self.assertRaises(AdwError) as caught:
                record_evidence_from_receipts(
                    item, duplicate, producer["ref"], lead["ref"], receipt_root,
                    current.audit["sequence"], current.audit["head"],
                )
            self.assertEqual("authority_required", caught.exception.kind)

    def test_actual_command_result_accepts_configured_absolute_repository_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = root / "delivery" / "AVOD-1"
            repository = root / "director2-aws"
            repository.mkdir()
            (item / ".adw" / "transactions").mkdir(parents=True)
            state = valid_state()
            state["repository"] = str(repository)
            state, evidence = write_genesis(item, state=state)
            command = [sys.executable, "-c", "print('real-check-output')"]
            snapshot = self.register_test_design_commands(item, state, {
                "real-check": {"argv": command, "expected_exit_codes": [0], "timeout_seconds": 10},
            })

            other_repository = root / "other" / "director2-aws"
            other_repository.mkdir(parents=True)
            with self.assertRaises(AdwError) as caught:
                run_evidence_command(
                    item, [sys.executable, "-c", "print('wrong-root')"], other_repository,
                    "E-WRONG-ROOT", "test:wrong-root", [], [0], "REQUEST-WRONG-ROOT", "lead/session-1",
                    state["audit"]["sequence"], state["audit"]["head"], timeout_seconds=10,
                )
            self.assertEqual("unsafe_path", caught.exception.kind)

            result = run_evidence_command(
                item, command, repository,
                "E-COMMAND", "command:real-check", [], [0], "REQUEST-COMMAND", "lead/session-1",
                snapshot.audit["sequence"], snapshot.audit["head"], timeout_seconds=10,
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

            self.assertEqual("E-COMMAND", result["evidence_id"])
            recorded = read_consistent_snapshot(item).evidence["evidence_index"][-1]
            self.assertEqual("pass", recorded["result_status"])
            artifact = json.loads((item / recorded["artifact_ref"]).read_text())
            self.assertEqual(0, artifact["exit_code"])
            self.assertIn("real-check-output", artifact["stdout"])

    def test_secret_bearing_command_output_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = root / "delivery" / "AVOD-1"
            repository = root / "director2-aws"
            repository.mkdir()
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            command = [sys.executable, "-c", "print('Authorization: Bearer exposed-value')"]
            snapshot = self.register_test_design_commands(item, state, {
                "secret-output": {"argv": command, "expected_exit_codes": [0], "timeout_seconds": 10},
            })

            with self.assertRaises(AdwError) as caught:
                run_evidence_command(
                    item, command, repository,
                    "E-SECRET", "command:secret-output", [], [0], "REQUEST-SECRET", "lead/session-1",
                    snapshot.audit["sequence"], snapshot.audit["head"], timeout_seconds=10,
                )

            self.assertEqual("unsafe_evidence", caught.exception.kind)
            self.assertEqual(2, read_consistent_snapshot(item).audit["sequence"])

    def test_actual_unexpected_exit_is_recorded_as_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = root / "delivery" / "AVOD-1"
            repository = root / "director2-aws"
            repository.mkdir()
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            command = [sys.executable, "-c", "raise SystemExit(3)"]
            snapshot = self.register_test_design_commands(item, state, {
                "failed-command": {"argv": command, "expected_exit_codes": [0], "timeout_seconds": 10},
            })

            run_evidence_command(
                item, command, repository,
                "E-FAILED-COMMAND", "command:failed-command", [], [0], "REQUEST-FAILED",
                "lead/session-1", snapshot.audit["sequence"], snapshot.audit["head"],
                timeout_seconds=10,
            )

            recorded = read_consistent_snapshot(item).evidence["evidence_index"][-1]
            self.assertEqual("fail", recorded["result_status"])
            artifact = json.loads((item / recorded["artifact_ref"]).read_text())
            self.assertEqual(3, artifact["exit_code"])

    def test_correction_attempt_numbers_are_derived_and_exhaust_at_the_configured_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            root_artifact = b'{"root_cause":"RC-1"}\n'
            root = valid_support_record("E-RC-1", root_artifact, state="TDD", evidence_type="root_cause_record", producer_role="lead_agent")
            root.update({"root_cause_relation": "new", "root_cause_ids": ["RC-1"], "parent_root_cause_ids": []})
            evidence["evidence_index"] = [root]
            write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-RC-1.json").write_bytes(root_artifact)

            for number in range(1, 5):
                snapshot = read_consistent_snapshot(item)
                artifact = canonical_json({"attempt": number})
                attempt = {
                    "id": "E-ATTEMPT-%d" % number, "type": "correction_attempt", "work_item": "AVOD-1",
                    "state": "TDD", "review_pass": None, "observed_at": "2026-01-0%dT00:00:00.000000Z" % (number + 1),
                    "result_status": "pass", "validity_status": "current", "producer_role": "lead_agent",
                    "producer_ref": "lead/run-1", "producer_proof_ref": "receipt/attempt-%d" % number,
                    "source_ref": "attempt:%d" % number, "artifact_ref": "artifacts/evidence/E-ATTEMPT-%d.json" % number,
                    "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(), "input_revisions": {},
                    "supports": ["E-RC-1"], "historical_supports": [], "revision_transition": None, "supersedes": [],
                    "invalidation_reason": None, "decision": "correction_attempt_started", "root_cause_ids": ["RC-1"],
                    "loop_policy_revision": snapshot.state["loop_policy"]["policy_revision"],
                }
                if number <= 3:
                    record_evidence(item, attempt, artifact, lambda candidate: True, "REQUEST-A-%d" % number,
                                    snapshot.audit["sequence"], snapshot.audit["head"], "lead/run-1")
                    recorded = read_consistent_snapshot(item).evidence["evidence_index"][-1]
                    self.assertEqual(number, recorded["attempt_numbers"]["RC-1"])
                else:
                    with self.assertRaises(AdwError) as caught:
                        record_evidence(item, attempt, artifact, lambda candidate: True, "REQUEST-A-4",
                                        snapshot.audit["sequence"], snapshot.audit["head"], "lead/run-1")
                    self.assertEqual("loop_exhausted", caught.exception.kind)

    def test_rejects_evidence_without_host_producer_proof(self):
        record = {
            "id": "E-1", "type": "command_result", "work_item": "AVOD-1", "state": "TDD", "review_pass": None, "producer_role": "qa_tool",
            "producer_ref": "runner-1", "producer_proof_ref": "", "recorded_by": "lead/run-1",
            "source_ref": "runner:1", "input_revisions": {}, "validity_status": "current",
        }
        with self.assertRaises(AdwError) as caught:
            validate_evidence_record(record, "AVOD-1")
        self.assertEqual("invalid_input", caught.exception.kind)

    def test_rejects_evidence_bound_to_a_stale_revision(self):
        record = {
            "id": "E-1", "type": "command_result", "work_item": "AVOD-1", "state": "TDD", "review_pass": None, "producer_role": "qa_tool",
            "producer_ref": "runner-1", "producer_proof_ref": "proof-1", "recorded_by": "lead/run-1",
            "source_ref": "runner:1", "input_revisions": {"change": "REV-OLD"},
            "result_status": "pass", "validity_status": "current", "artifact_ref": "artifacts/results/1.json",
            "integrity_ref": "sha256:" + "a" * 64,
        }
        with self.assertRaises(AdwError) as caught:
            validate_evidence_record(record, "AVOD-1", {"change": "REV-CURRENT"})
        self.assertEqual("invalid_control_block", caught.exception.kind)

    def test_rejects_dangling_evidence_support(self):
        record = {
            "id": "E-2", "type": "gate_decision", "work_item": "AVOD-1", "state": "CODE_QUALITY_GATE", "review_pass": None, "producer_role": "judge_agent",
            "producer_ref": "judge-1", "producer_proof_ref": "proof-2", "recorded_by": "lead/run-1",
            "source_ref": "review:2", "input_revisions": {}, "result_status": "pass",
            "validity_status": "current", "supports": ["E-MISSING"], "historical_supports": [],
            "artifact_ref": "artifacts/reviews/2.json", "integrity_ref": "sha256:" + "b" * 64,
        }
        with self.assertRaises(AdwError) as caught:
            validate_evidence_record(record, "AVOD-1", {}, {"E-1"})
        self.assertEqual("invalid_control_block", caught.exception.kind)

    def test_rejects_evidence_without_artifact_integrity(self):
        record = {
            "id": "E-1", "type": "command_result", "work_item": "AVOD-1", "state": "TDD", "review_pass": None, "producer_role": "qa_tool",
            "producer_ref": "runner-1", "producer_proof_ref": "proof-1", "recorded_by": "lead/run-1",
            "source_ref": "runner:1", "input_revisions": {}, "result_status": "pass", "validity_status": "current",
            "artifact_ref": "artifacts/results/test.json", "integrity_ref": "not-a-digest",
        }
        with self.assertRaises(AdwError) as caught:
            validate_evidence_record(record, "AVOD-1")
        self.assertEqual("invalid_control_block", caught.exception.kind)

    def test_records_verified_revision_bound_evidence_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"]["change"] = "REV-CHANGE"
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            artifact = b'{"exit_code":0}\n'
            record = {
                "id": "E-TEST-1", "type": "command_result", "work_item": "AVOD-1", "state": "TDD",
                "review_pass": None, "observed_at": "2026-01-02T00:00:00.000000Z", "result_status": "pass",
                "validity_status": "current", "producer_role": "qa_tool", "producer_ref": "tool/run-1",
                "producer_proof_ref": "receipt/run-1", "source_ref": "command:test-1",
                "artifact_ref": "artifacts/evidence/E-TEST-1.json",
                "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(),
                "input_revisions": {"change": "REV-CHANGE"}, "supports": [], "historical_supports": [],
                "revision_transition": None, "supersedes": [], "invalidation_reason": None,
            }

            result = record_evidence(
                item, record, artifact, lambda candidate: candidate["producer_proof_ref"] == "receipt/run-1",
                "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

            snapshot = read_consistent_snapshot(item)
            self.assertEqual("E-TEST-1", result["evidence_id"])
            self.assertEqual("E-TEST-1", snapshot.evidence["evidence_index"][0]["id"])
            self.assertEqual(2, snapshot.evidence["evidence_index"][0]["audit_sequence"])
            self.assertEqual(artifact, (item / "artifacts" / "evidence" / "E-TEST-1.json").read_bytes())

    def test_unverified_producer_proof_leaves_no_evidence_or_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            artifact = b"{}\n"
            record = {
                "id": "E-TEST-1", "type": "command_result", "work_item": "AVOD-1", "state": "TDD",
                "review_pass": None, "observed_at": "2026-01-02T00:00:00.000000Z", "result_status": "pass",
                "validity_status": "current", "producer_role": "qa_tool", "producer_ref": "tool/run-1",
                "producer_proof_ref": "unverified", "source_ref": "command:test-1",
                "artifact_ref": "artifacts/evidence/E-TEST-1.json", "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(),
                "input_revisions": {}, "supports": [], "historical_supports": [], "revision_transition": None,
                "supersedes": [], "invalidation_reason": None,
            }
            with self.assertRaises(AdwError) as caught:
                record_evidence(item, record, artifact, lambda candidate: False, "REQUEST-2", 1, state["audit"]["head"], "lead/run-2")

            self.assertEqual("authority_required", caught.exception.kind)
            self.assertEqual([], read_consistent_snapshot(item).evidence["evidence_index"])
            self.assertFalse((item / record["artifact_ref"]).exists())

    def test_raw_command_result_cannot_claim_a_gate(self):
        record = {
            "id": "E-1", "type": "command_result", "work_item": "AVOD-1", "state": "TDD", "review_pass": None,
            "producer_role": "qa_tool", "producer_ref": "tool/run-1", "producer_proof_ref": "proof-1",
            "recorded_by": "lead/run-1", "source_ref": "command:test", "artifact_ref": "artifacts/evidence/E-1.json",
            "integrity_ref": "sha256:" + "a" * 64, "input_revisions": {}, "result_status": "pass",
            "validity_status": "current", "supports": [], "historical_supports": [], "gate": "tdd_pass",
            "decision": "tdd_accepted",
        }
        with self.assertRaises(AdwError) as caught:
            validate_evidence_record(record, "AVOD-1")
        self.assertEqual("invalid_control_block", caught.exception.kind)

    def test_gate_decision_cannot_omit_required_revisions(self):
        record = {
            "id": "E-1", "type": "gate_decision", "work_item": "AVOD-1", "state": "TDD", "review_pass": None,
            "producer_role": "lead_agent", "producer_ref": "lead/run-1", "producer_proof_ref": "proof-1",
            "recorded_by": "lead/run-1", "source_ref": "decision:tdd", "artifact_ref": "artifacts/evidence/E-1.json",
            "integrity_ref": "sha256:" + "a" * 64, "input_revisions": {"change": "REV-CHANGE"},
            "result_status": "pass", "validity_status": "current", "supports": [], "historical_supports": [],
            "supersedes": [], "gate": "tdd_pass", "decision": "tdd_accepted",
        }
        with self.assertRaises(AdwError) as caught:
            validate_evidence_record(record, "AVOD-1")
        self.assertEqual("invalid_control_block", caught.exception.kind)

    def test_verified_decision_updates_only_its_gate_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"]["specification"] = "REV-SPEC"
            support_artifact = b'{"snapshot":true}\n'
            evidence["evidence_index"] = [valid_support_record("E-SNAPSHOT", support_artifact, revisions={"specification": "REV-SPEC"})]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-SNAPSHOT.json").write_bytes(support_artifact)
            artifact = b'{"approved":true}\n'
            record = {
                "id": "E-APPROVAL", "type": "approval_decision", "work_item": "AVOD-1", "state": "SPECIFY",
                "review_pass": None, "observed_at": "2026-01-02T00:00:00.000000Z", "result_status": "pass",
                "validity_status": "current", "producer_role": "ticket_owner", "producer_ref": "human/user-1",
                "producer_proof_ref": "receipt/approval-1", "source_ref": "approval:1",
                "artifact_ref": "artifacts/evidence/E-APPROVAL.json", "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(),
                "input_revisions": {"specification": "REV-SPEC"}, "supports": ["E-SNAPSHOT"],
                "historical_supports": [], "revision_transition": None, "supersedes": [], "invalidation_reason": None,
                "gate": "specification_approval", "decision": "specification_approved",
            }
            record_evidence(item, record, artifact, lambda candidate: True, "REQUEST-2", 1, state["audit"]["head"], "lead/run-2")

            gates = read_consistent_snapshot(item).state["gate_evidence"]
            self.assertEqual("E-APPROVAL", gates["specification_approval"])
            self.assertTrue(all(value is None for name, value in gates.items() if name != "specification_approval"))


class TransitionValidationTests(unittest.TestCase):
    def test_quality_gates_have_concrete_state_names(self):
        self.assertNotIn("REVIEW", adw_core.STATES)
        self.assertIn("CODE_QUALITY_GATE", adw_core.STATES)
        self.assertIn("DELIVERY_GATE", adw_core.STATES)
        self.assertEqual(
            ("CODE_QUALITY_GATE", None),
            adw_core.GATE_REQUIREMENTS["first_review"][3:5],
        )
        self.assertEqual(
            ("DELIVERY_GATE", None),
            adw_core.GATE_REQUIREMENTS["final_review"][3:5],
        )

    def test_corrected_tdd_cannot_enter_code_quality_gate_without_submission_accounting(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            state["gate_evidence"]["tdd_pass"] = "E-TDD"
            state["transition_history"] = [{
                "audit_sequence": 1, "transaction_id": "TX-CORRECT", "request_id": "REQUEST-CORRECT",
                "recorded_at": "2026-01-01T00:00:00.000000Z", "kind": "correct", "from_state": "CODE_QUALITY_GATE",
                "from_review_pass": None, "to_state": "TDD", "to_review_pass": None,
                "decision_evidence_id": "E-RETURN", "supporting_evidence_ids": ["E-RETURN"],
                "reason": "Finding", "next_action": "Correct", "owner": "developer",
                "correction_attempt_ids": [], "correction_loop_sequence": None,
            }]
            write_genesis(item, state=state, evidence=evidence)
            with self.assertRaises(AdwError) as caught:
                validate_transition(item, "CODE_QUALITY_GATE", None, "E-TDD")
            self.assertEqual("loop_accounting_required", caught.exception.kind)

    def test_corrected_tdd_submission_derives_one_global_code_quality_loop(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            state["current_revisions"] = {domain: "REV-" + domain.upper() for domain in state["current_revisions"]}
            state["gate_evidence"]["tdd_pass"] = "E-TDD"
            state["transition_history"] = [{
                "audit_sequence": 1, "transaction_id": "TX-CORRECT", "request_id": "REQUEST-CORRECT",
                "recorded_at": "2026-01-01T00:00:00.000000Z", "kind": "correct", "from_state": "CODE_QUALITY_GATE",
                "from_review_pass": None, "to_state": "TDD", "to_review_pass": None,
                "decision_evidence_id": "E-RETURN", "supporting_evidence_ids": ["E-RETURN"],
                "reason": "Finding", "next_action": "Correct", "owner": "developer",
                "correction_attempt_ids": [], "correction_loop_sequence": None,
            }]
            support_artifact = b'{"tests":"pass"}\n'
            red_artifact = b'{"tests":"expected-failure"}\n'
            gate_artifact = b'{"decision":"tdd_accepted"}\n'
            attempt_artifact = b'{"attempt":1}\n'
            support = valid_support_record("E-SUPPORT", support_artifact, state="TDD", revisions=copy.deepcopy(state["current_revisions"]))
            red = valid_support_record("E-RED", red_artifact, state="TDD", result_status="fail", revisions=copy.deepcopy(state["current_revisions"]))
            red["observed_at"] = "2025-12-31T00:00:00.000000Z"
            attempt = valid_support_record("E-ATTEMPT", attempt_artifact, state="TDD", revisions=copy.deepcopy(state["current_revisions"]), evidence_type="correction_attempt", producer_role="lead_agent")
            attempt.update({"decision": "correction_attempt_started", "root_cause_ids": ["RC-1"], "loop_policy_revision": "LOOP-1", "attempt_numbers": {"RC-1": 1}})
            gate = {
                "id": "E-TDD", "type": "gate_decision", "work_item": "AVOD-1", "state": "TDD", "review_pass": None,
                "producer_role": "lead_agent", "producer_ref": "lead/run-1", "producer_proof_ref": "receipt/tdd",
                "recorded_by": "lead/run-1", "source_ref": "decision:tdd", "artifact_ref": "artifacts/evidence/E-TDD.json",
                "integrity_ref": "sha256:" + hashlib.sha256(gate_artifact).hexdigest(), "input_revisions": copy.deepcopy(state["current_revisions"]),
                "result_status": "pass", "validity_status": "current", "supports": ["E-SUPPORT"], "historical_supports": ["E-RED"],
                "supersedes": [], "gate": "tdd_pass", "decision": "tdd_accepted",
            }
            evidence["evidence_index"] = [red, support, attempt, gate]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            for name, artifact in (("E-RED", red_artifact), ("E-SUPPORT", support_artifact), ("E-ATTEMPT", attempt_artifact), ("E-TDD", gate_artifact)):
                (item / "artifacts" / "evidence" / (name + ".json")).write_bytes(artifact)

            token = validate_transition(item, "CODE_QUALITY_GATE", None, "E-TDD", correction_attempt_ids=["E-ATTEMPT"])
            self.assertEqual(1, token["correction_loop_sequence"])
            transition_work_item(item, token, "Correction ready", "Code quality gate", "lead/run-1", "REQUEST-2",
                                 state["audit"]["sequence"], state["audit"]["head"], "lead/run-1")
            history = read_consistent_snapshot(item).state["transition_history"][-1]
            self.assertEqual(["E-ATTEMPT"], history["correction_attempt_ids"])
            self.assertEqual(1, history["correction_loop_sequence"])

            snapshot = read_consistent_snapshot(item)
            proposed_state = copy.deepcopy(snapshot.state)
            proposed_state["state"], proposed_state["review_pass"] = "TDD", None
            template = copy.deepcopy(proposed_state["transition_history"][-1])
            for sequence in range(2, 6):
                entry = copy.deepcopy(template)
                entry.update({
                    "audit_sequence": sequence, "transaction_id": "TX-LOOP-%d" % sequence,
                    "request_id": "REQUEST-LOOP-%d" % sequence, "correction_attempt_ids": ["E-OLD-%d" % sequence],
                    "correction_loop_sequence": sequence,
                })
                proposed_state["transition_history"].append(entry)
            correction = copy.deepcopy(template)
            correction.update({
                "kind": "correct", "from_state": "CODE_QUALITY_GATE", "from_review_pass": None, "to_state": "TDD",
                "to_review_pass": None, "correction_attempt_ids": [], "correction_loop_sequence": None,
            })
            proposed_state["transition_history"].append(correction)
            proposed_evidence = copy.deepcopy(snapshot.evidence)
            proposed_evidence["evidence_index"].append({"id": "E-ATTEMPT-2", "type": "correction_attempt"})
            commit_transaction(
                item, proposed_state, proposed_evidence, expected_sequence=snapshot.audit["sequence"], expected_head=snapshot.audit["head"],
                transaction_id="TX-LOOP-SETUP", request_id="REQUEST-LOOP-SETUP", command="test-setup", safe_arguments={},
                lead_run_ref="lead/run-1", semantic_ids=["E-ATTEMPT-2"], intended_result={"setup": True},
                now=datetime(2026, 1, 10, tzinfo=timezone.utc),
            )
            with self.assertRaises(AdwError) as caught:
                validate_transition(item, "CODE_QUALITY_GATE", None, "E-TDD", correction_attempt_ids=["E-ATTEMPT-2"])
            self.assertEqual("loop_exhausted", caught.exception.kind)

    def test_rejects_malformed_transition_history(self):
        state, evidence = valid_state(), valid_evidence()
        state["transition_history"] = ["malformed"]
        with self.assertRaises(AdwError) as caught:
            validate_control_pair(state, evidence)
        self.assertEqual("invalid_control_block", caught.exception.kind)

    def test_rejects_a_forged_transition_token_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            token = {"token": "sha256:" + "0" * 64}
            with self.assertRaises(AdwError) as caught:
                transition_work_item(Path(temp, "missing"), token, "reason", "next", "owner", "REQUEST-1", 1,
                                     "sha256:" + "a" * 64, "lead/run-1")
            self.assertEqual("invalid_transition", caught.exception.kind)

    def test_rejects_skipping_from_tdd_to_delivery_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            write_genesis(item, state=state, evidence=evidence)

            with self.assertRaises(AdwError) as caught:
                validate_transition(item, "DELIVERY_GATE", None, None)
            self.assertEqual("invalid_transition", caught.exception.kind)

    def test_rejects_a_gate_pointer_to_missing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["gate_evidence"]["specification_approval"] = "E-MISSING"
            write_genesis(item, state=state, evidence=evidence)

            with self.assertRaises(AdwError) as caught:
                validate_transition(item, "TEST_DESIGN", None, "E-MISSING")
            self.assertEqual("invalid_transition", caught.exception.kind)

    def test_forward_gate_cannot_convert_failed_support_to_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"]["specification"] = "REV-SPEC"
            state["gate_evidence"]["specification_approval"] = "E-APPROVAL"
            support_artifact = b'{"result":"fail"}\n'
            decision_artifact = b'{"approved":true}\n'
            support = valid_support_record("E-FAIL", support_artifact, result_status="fail", revisions={"specification": "REV-SPEC"})
            decision = {
                "id": "E-APPROVAL", "type": "approval_decision", "work_item": "AVOD-1", "state": "SPECIFY", "review_pass": None,
                "producer_role": "ticket_owner", "producer_ref": "human/user-1", "producer_proof_ref": "receipt/1",
                "recorded_by": "lead/run-1", "source_ref": "approval:1", "artifact_ref": "artifacts/evidence/E-APPROVAL.json",
                "integrity_ref": "sha256:" + hashlib.sha256(decision_artifact).hexdigest(), "input_revisions": {"specification": "REV-SPEC"},
                "result_status": "pass", "validity_status": "current", "supports": ["E-FAIL"], "historical_supports": [],
                "supersedes": [], "gate": "specification_approval", "decision": "specification_approved",
            }
            write_genesis(item, state=state, evidence={**evidence, "evidence_index": [support, decision]})
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-FAIL.json").write_bytes(support_artifact)
            (item / "artifacts" / "evidence" / "E-APPROVAL.json").write_bytes(decision_artifact)

            with self.assertRaises(AdwError) as caught:
                validate_transition(item, "TEST_DESIGN", None, "E-APPROVAL")
            self.assertEqual("invalid_transition", caught.exception.kind)

    def test_validates_specification_approval_movement(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"]["specification"] = "REV-SPEC"
            support_artifact = b'{"snapshot":true}\n'
            evidence["evidence_index"] = [valid_support_record("E-SNAPSHOT", support_artifact, revisions={"specification": "REV-SPEC"})]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-SNAPSHOT.json").write_bytes(support_artifact)
            artifact = b'{"approved":true}\n'
            record = {
                "id": "E-APPROVAL", "type": "approval_decision", "work_item": "AVOD-1", "state": "SPECIFY",
                "review_pass": None, "observed_at": "2026-01-02T00:00:00.000000Z", "result_status": "pass",
                "validity_status": "current", "producer_role": "ticket_owner", "producer_ref": "human/user-1",
                "producer_proof_ref": "receipt/approval-1", "source_ref": "approval:1",
                "artifact_ref": "artifacts/evidence/E-APPROVAL.json", "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(),
                "input_revisions": {"specification": "REV-SPEC"}, "supports": ["E-SNAPSHOT"],
                "historical_supports": [], "revision_transition": None, "supersedes": [], "invalidation_reason": None,
                "gate": "specification_approval", "decision": "specification_approved",
            }
            record_evidence(item, record, artifact, lambda candidate: True, "REQUEST-2", 1, state["audit"]["head"], "lead/run-2")

            token = validate_transition(item, "TEST_DESIGN", None, "E-APPROVAL")
            self.assertEqual("advance", token["kind"])
            self.assertEqual("sha256:", token["token"][:7])
            result = transition_work_item(
                item, token, "Specification approved", "Design scenario verification", "lead/run-2",
                "REQUEST-3", token["sequence"], token["head"], "lead/run-2",
                now=datetime(2026, 1, 3, tzinfo=timezone.utc),
            )
            self.assertEqual("TEST_DESIGN", result["state"])
            self.assertEqual("TEST_DESIGN", read_consistent_snapshot(item).state["state"])

    def test_block_transition_preserves_origin_and_resume_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "TDD"
            support_artifact = b'{"failed":true}\n'
            evidence["evidence_index"] = [valid_support_record("E-FAIL", support_artifact, state="TDD", result_status="fail")]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-FAIL.json").write_bytes(support_artifact)
            artifact = b'{"blocked":true}\n'
            record = {
                "id": "E-BLOCK", "type": "gate_decision", "work_item": "AVOD-1", "state": "TDD", "review_pass": None,
                "observed_at": "2026-01-02T00:00:00.000000Z", "result_status": "pass", "validity_status": "current",
                "producer_role": "lead_agent", "producer_ref": "lead/run-1", "producer_proof_ref": "receipt/block-1",
                "source_ref": "decision:block", "artifact_ref": "artifacts/evidence/E-BLOCK.json",
                "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(), "input_revisions": {},
                "supports": ["E-FAIL"], "historical_supports": [], "revision_transition": None, "supersedes": [],
                "invalidation_reason": None, "decision": "blocked",
            }
            record_evidence(item, record, artifact, lambda candidate: True, "REQUEST-2", 1, state["audit"]["head"], "lead/run-1")
            snapshot = read_consistent_snapshot(item)
            token = validate_transition(item, "BLOCKED", None, "E-BLOCK", "TDD", None)
            transition_work_item(item, token, "Required prerequisite unavailable", "Resolve prerequisite", "developer",
                                 "REQUEST-3", snapshot.audit["sequence"], snapshot.audit["head"], "lead/run-1")

            blocked = read_consistent_snapshot(item).state
            self.assertEqual("BLOCKED", blocked["state"])
            self.assertEqual("TDD", blocked["blocked_from_state"])
            self.assertEqual("TDD", blocked["resume_state"])
            resume_artifact = b'{"resolved":true}\n'
            resume_record = {
                "id": "E-RESUME", "type": "gate_decision", "work_item": "AVOD-1", "state": "BLOCKED", "review_pass": None,
                "observed_at": "2026-01-04T00:00:00.000000Z", "result_status": "pass", "validity_status": "current",
                "producer_role": "lead_agent", "producer_ref": "lead/run-1", "producer_proof_ref": "receipt/resume-1",
                "source_ref": "decision:resume", "artifact_ref": "artifacts/evidence/E-RESUME.json",
                "integrity_ref": "sha256:" + hashlib.sha256(resume_artifact).hexdigest(), "input_revisions": {},
                "supports": ["E-BLOCK"], "historical_supports": [], "revision_transition": None, "supersedes": [],
                "invalidation_reason": None, "decision": "resume_accepted",
            }
            snapshot = read_consistent_snapshot(item)
            record_evidence(item, resume_record, resume_artifact, lambda candidate: True, "REQUEST-4", snapshot.audit["sequence"], snapshot.audit["head"], "lead/run-1")
            snapshot = read_consistent_snapshot(item)
            resume_token = validate_transition(item, "TDD", None, "E-RESUME")
            transition_work_item(item, resume_token, "Prerequisite resolved", "Resume TDD", "developer",
                                 "REQUEST-5", snapshot.audit["sequence"], snapshot.audit["head"], "lead/run-1")

            resumed = read_consistent_snapshot(item).state
            self.assertEqual("TDD", resumed["state"])
            self.assertIsNone(resumed["blocked_from_state"])
            self.assertEqual([], resumed["blocker_ids"])

    def test_validates_smallest_corrective_route_to_tdd(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"], state["review_pass"] = "CODE_QUALITY_GATE", None
            support_artifact = b'{"finding":true}\n'
            evidence["evidence_index"] = [valid_support_record("E-FINDING", support_artifact, state="CODE_QUALITY_GATE", result_status="fail", evidence_type="review_finding", producer_role="judge_agent")]
            state, evidence = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-FINDING.json").write_bytes(support_artifact)
            artifact = b'{"route":"TDD"}\n'
            record = {
                "id": "E-RETURN", "type": "gate_decision", "work_item": "AVOD-1", "state": "CODE_QUALITY_GATE", "review_pass": None,
                "observed_at": "2026-01-02T00:00:00.000000Z", "result_status": "pass", "validity_status": "current",
                "producer_role": "judge_agent", "producer_ref": "judge/run-1", "producer_proof_ref": "receipt/return-1",
                "source_ref": "decision:return", "artifact_ref": "artifacts/evidence/E-RETURN.json",
                "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(), "input_revisions": {},
                "supports": ["E-FINDING"], "historical_supports": [], "revision_transition": None, "supersedes": [],
                "invalidation_reason": None, "decision": "return_to_tdd",
            }
            record_evidence(item, record, artifact, lambda candidate: True, "REQUEST-2", 1, state["audit"]["head"], "lead/run-1")

            token = validate_transition(item, "TDD", None, "E-RETURN")
            self.assertEqual("correct", token["kind"])

    def test_complete_forward_workflow_uses_every_gate_in_order(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"] = {domain: "REV-" + domain.upper() for domain in state["current_revisions"]}
            support_artifact = b'{"support":true}\n'
            red_artifact = b'{"test":"expected-failure"}\n'
            green_artifact = b'{"test":"pass"}\n'
            local_qa_artifact = b'{"local_qa":"pass"}\n'
            mutation_artifact = b'{"mutation":"pass"}\n'
            red = valid_support_record("E-RED", red_artifact, state="TDD", result_status="fail", revisions=copy.deepcopy(state["current_revisions"]))
            green = valid_support_record("E-GREEN", green_artifact, state="TDD", revisions=copy.deepcopy(state["current_revisions"]))
            local_qa = valid_support_record(
                "E-LOCAL-QA", local_qa_artifact, state="LOWER_ENV_VERIFY",
                revisions=copy.deepcopy(state["current_revisions"]), evidence_type="local_qa_result",
            )
            mutation = valid_support_record(
                "E-MUTATION", mutation_artifact, state="MUTATION_GATE",
                revisions=copy.deepcopy(state["current_revisions"]), evidence_type="mutation_result",
                producer_role="mutation_tool",
            )
            red["observed_at"] = "2026-01-01T00:00:00.000000Z"
            green["observed_at"] = "2026-01-02T00:00:00.000000Z"
            evidence["evidence_index"] = [
                valid_support_record("E-SUPPORT", support_artifact, revisions=copy.deepcopy(state["current_revisions"])),
                red, green, local_qa, mutation,
            ]
            write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-SUPPORT.json").write_bytes(support_artifact)
            (item / "artifacts" / "evidence" / "E-RED.json").write_bytes(red_artifact)
            (item / "artifacts" / "evidence" / "E-GREEN.json").write_bytes(green_artifact)
            (item / "artifacts" / "evidence" / "E-LOCAL-QA.json").write_bytes(local_qa_artifact)
            (item / "artifacts" / "evidence" / "E-MUTATION.json").write_bytes(mutation_artifact)
            steps = [
                ("specification_approval", "approval_decision", "specification_approved", "ticket_owner", "TEST_DESIGN", None),
                ("test_design_pass", "gate_decision", "test_design_accepted", "lead_agent", "TDD", None),
                ("tdd_pass", "gate_decision", "tdd_accepted", "lead_agent", "CODE_QUALITY_GATE", None),
                ("first_review", "gate_decision", "continue_to_local_qa", "judge_agent", "LOWER_ENV_VERIFY", None),
                ("local_qa_pass", "gate_decision", "local_qa_accepted", "lead_agent", "MUTATION_GATE", None),
                ("mutation_decision", "gate_decision", "mutation_accepted", "lead_agent", "DELIVERY_GATE", None),
                ("final_review", "gate_decision", "approved", "judge_agent", "COMPLETE", None),
            ]
            for number, (gate, evidence_type, decision, role, target, target_pass) in enumerate(steps, 1):
                snapshot = read_consistent_snapshot(item)
                evidence_id = "E-GATE-%d" % number
                artifact = canonical_json({"decision": decision})
                record = {
                    "id": evidence_id, "type": evidence_type, "work_item": "AVOD-1", "state": snapshot.state["state"],
                    "review_pass": snapshot.state["review_pass"], "observed_at": "2026-01-%02dT00:00:00.000000Z" % (number + 1),
                    "result_status": "pass", "validity_status": "current", "producer_role": role,
                    "producer_ref": "producer/run-%d" % number, "producer_proof_ref": "receipt/%d" % number,
                    "source_ref": "decision:%d" % number, "artifact_ref": "artifacts/evidence/%s.json" % evidence_id,
                    "integrity_ref": "sha256:" + hashlib.sha256(artifact).hexdigest(),
                    "input_revisions": copy.deepcopy(snapshot.state["current_revisions"]),
                    "supports": (
                        ["E-GREEN"] if gate == "tdd_pass" else
                        ["E-GATE-3"] if gate == "first_review" else
                        ["E-LOCAL-QA"] if gate == "local_qa_pass" else
                        ["E-MUTATION"] if gate == "mutation_decision" else
                        ["E-GATE-4", "E-GATE-5", "E-GATE-6"] if gate == "final_review" else
                        ["E-SUPPORT"]
                    ),
                    "historical_supports": ["E-RED"] if gate == "tdd_pass" else [],
                    "revision_transition": None, "supersedes": [], "invalidation_reason": None,
                    "gate": gate, "decision": decision,
                }
                record_evidence(item, record, artifact, lambda candidate: True, "REQUEST-E-%d" % number,
                                snapshot.audit["sequence"], snapshot.audit["head"], "lead/run-1")
                snapshot = read_consistent_snapshot(item)
                token = validate_transition(item, target, target_pass, evidence_id)
                transition_work_item(item, token, "Gate accepted", "Continue workflow", "lead/run-1",
                                     "REQUEST-T-%d" % number, snapshot.audit["sequence"], snapshot.audit["head"], "lead/run-1")

            completed = read_consistent_snapshot(item)
            self.assertEqual("COMPLETE", completed.state["state"])
            self.assertEqual(7, len(completed.state["transition_history"]))


class RevisionTests(unittest.TestCase):
    @staticmethod
    def write_complete_specification_package(item):
        documents = {
            "01-scope.md": """# Scope Statement

**Ticket:** AVOD-458 — Support freeWithAds uxPromoTag for TV series
**Repo:** director2-aws
**Type:** Behavior change
**Goal:** Return freeWithAds for an eligible TV series.
**Done when:** contentSearch returns the series freeWithAds tag and advert window.
**Constraints:** Preserve non-series behavior and use the supported harness.
**Prior context:** Existing season behavior is the reusable baseline.
**Out of scope:** Other promo tags and scoring.

## Existing Work and TDD Entry

**Ticket implementation at intake:** none
**Ticket tests at intake:** none
**RED strategy:** normal-red-first
**Baseline evidence:** `git status --short` and the ticket diff show no ticket implementation or test changes.
""",
            "02-investigation.md": """# Investigation: Support freeWithAds for TV series

**What the ticket is asking:** Publish the same observable AVOD tag for eligible series that existing content types expose.

## Current behavior

### suite/dis/src/MediaContentBuildHelper.java:687–707

```java
private static void createUxPromoTags(String contentId) {
    setAvodUxPromoTagForSeason(contentId);
}
```

The verified publish path handles seasons but has no series branch.

## What already exists to reuse

### suite/dis/src/MediaContentBuildHelper.java:709–733

```java
private static void setAvodUxPromoTagForSeason(String contentId) {
    // Existing bottom-up tag construction.
}
```

Reuse the existing tag construction and add the extra container hop required by a series.

## Where the change lives

| File | Lines | What changes |
|---|---:|---|
| `suite/dis/src/MediaContentBuildHelper.java` | 687–733 | Add the series path beside the season path. |
| `suite/dis/test/test-series-avod.xml` | new | Prove the series response and advert window. |

## What is missing

A verified series-to-season-to-episode lookup and a harness assertion against contentSearch.

## Open questions

None.
""",
            "03-roadmap.md": """# Plan: Support freeWithAds for TV series

**North Star:** The eligible series response exposes the approved tag and window.
**Ticket:** AVOD-458
**Overall:** next

## Steps

| # | Step | File(s) | Done when | Status |
|---:|---|---|---|---|
| 1 | Add the harness scenario | `suite/dis/test/test-series-avod.xml` | Supported harness run is RED for the missing series tag | next |
| 2 | Implement the smallest series path | `suite/dis/src/MediaContentBuildHelper.java` | The same harness run is GREEN | next |
| 3 | Run the full affected suite | `suite/dis` | No change-related failure remains | next |
| 4 | Run code review | change diff | All blocking findings are resolved | next |
| 5 | Complete local verification | local environment | Approved scenarios have recorded evidence | next |

## Risks

| Risk | Caught by |
|---|---|
| Duplicate season tag | Exact row-count assertion in Step 1 |
""",
            "04-code-guide.md": """# Code Change Guide + Test Plan: Support freeWithAds for TV series

## Files to change

| File | What changes |
|---|---|
| `suite/dis/src/MediaContentBuildHelper.java` | Add the series lookup beside the season implementation. |
| `suite/dis/test/test-series-avod.xml` | Add positive, negative, and duplicate-regression cases. |

## Pattern to follow

Follow `setAvodUxPromoTagForSeason` from `suite/dis/src/MediaContentBuildHelper.java:709`.

## What NOT to change

Do not change the contentSearch read path or advert eligibility rules.

## Config changes

None.

## Harness Test Plan

| Case | Setup | Action | Expected result |
|---|---|---|---|
| Eligible series | Series with one eligible episode | Publish and call contentSearch | freeWithAds and its window are returned |
| Ineligible series | Series without an eligible episode | Publish and call contentSearch | freeWithAds is absent |
| Duplicate regression | Season already has the matching tag | Publish its parent series | Exactly one matching row remains |
""",
            "specification.md": """# Specification: AVOD-458 — Support freeWithAds for TV series

## Ticket and Goal

Return freeWithAds for an eligible TV series without changing ineligible content.

## Scope and Constraints

The approved scope and exclusions are in [01-scope.md](01-scope.md).

## Configuration Resolution Record

Use the director2-aws repository profile and supported DIS harness; TEST_DESIGN must resolve the exact fixture and cleanup path.

## Specification Package

- [Investigation](02-investigation.md)
- [Roadmap](03-roadmap.md)
- [Code guide](04-code-guide.md)

## Acceptance Criteria

The series response contains the tag and active window, the negative case remains absent, and seasons do not gain duplicates.

## Gherkin Scenarios

```gherkin
Scenario: Eligible series exposes freeWithAds
  Given a series with an eligible descendant episode
  When the series is published and requested through contentSearch
  Then freeWithAds and its active advert window are returned
```

## Approval Record

Pending developer or ticket-owner approval of the recorded package revision.
""",
        }
        for name, contents in documents.items():
            (item / name).write_text(contents, encoding="utf-8")

    def test_rejects_an_incomplete_specification_package_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            (item / "specification.md").write_text("# Specification\n\nA shallow summary.\n", encoding="utf-8")

            with self.assertRaises(AdwError) as caught:
                adw_core.record_specification_package(
                    item, "Complete investigation and specification", "REQUEST-2",
                    state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("incomplete_specification", caught.exception.kind)
            self.assertEqual(1, read_consistent_snapshot(item).audit["sequence"])
            self.assertFalse((item / "artifacts" / "specification").exists())

    def test_rejects_a_specification_document_that_is_still_a_template(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            self.write_complete_specification_package(item)
            investigation = item / "02-investigation.md"
            investigation.write_text("<!-- ADW-TEMPLATE -->\n" + investigation.read_text(encoding="utf-8"), encoding="utf-8")

            with self.assertRaises(AdwError) as caught:
                adw_core.record_specification_package(
                    item, "Complete investigation and specification", "REQUEST-2",
                    state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("incomplete_specification", caught.exception.kind)
            self.assertIn("uncompleted template", str(caught.exception))

    def test_rejects_unverified_hedge_language_in_the_investigation(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            self.write_complete_specification_package(item)
            investigation = item / "02-investigation.md"
            investigation.write_text(
                investigation.read_text(encoding="utf-8") + "\nThe missing caller is probably in the same module.\n",
                encoding="utf-8",
            )

            with self.assertRaises(AdwError) as caught:
                adw_core.record_specification_package(
                    item, "Complete investigation and specification", "REQUEST-2",
                    state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("incomplete_specification", caught.exception.kind)
            self.assertIn("unverified hedge", str(caught.exception))

    def test_rejects_normal_red_strategy_when_ticket_implementation_already_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            self.write_complete_specification_package(item)
            scope = item / "01-scope.md"
            scope.write_text(
                scope.read_text(encoding="utf-8").replace(
                    "**Ticket implementation at intake:** none",
                    "**Ticket implementation at intake:** present",
                ),
                encoding="utf-8",
            )

            with self.assertRaises(AdwError) as caught:
                adw_core.record_specification_package(
                    item, "Complete investigation and specification", "REQUEST-2",
                    state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("incomplete_specification", caught.exception.kind)
            self.assertIn("normal-red-first", str(caught.exception))

    def test_accepts_isolated_clean_baseline_for_pre_existing_ticket_work(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            self.write_complete_specification_package(item)
            scope = item / "01-scope.md"
            scope.write_text(
                scope.read_text(encoding="utf-8")
                .replace("**Ticket implementation at intake:** none", "**Ticket implementation at intake:** present")
                .replace("**Ticket tests at intake:** none", "**Ticket tests at intake:** present")
                .replace("**RED strategy:** normal-red-first", "**RED strategy:** isolated-clean-baseline"),
                encoding="utf-8",
            )

            result = adw_core.record_specification_package(
                item, "Complete package with safe baseline strategy", "REQUEST-2",
                state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
            )

            self.assertTrue(result["revision_id"].startswith("REV-"))

    def test_rejects_red_strategies_that_do_not_match_the_intake_state(self):
        cases = (
            ("none", "none", "current-failing-test"),
            ("none", "none", "isolated-clean-baseline"),
            ("present", "present", "retrospective-reversal"),
        )
        for implementation, tests, strategy in cases:
            with self.subTest(strategy=strategy), tempfile.TemporaryDirectory() as temp:
                item = Path(temp, "AVOD-1")
                (item / ".adw" / "transactions").mkdir(parents=True)
                state, evidence = write_genesis(item)
                self.write_complete_specification_package(item)
                scope = item / "01-scope.md"
                scope.write_text(
                    scope.read_text(encoding="utf-8")
                    .replace("**Ticket implementation at intake:** none", "**Ticket implementation at intake:** " + implementation)
                    .replace("**Ticket tests at intake:** none", "**Ticket tests at intake:** " + tests)
                    .replace("**RED strategy:** normal-red-first", "**RED strategy:** " + strategy),
                    encoding="utf-8",
                )

                with self.assertRaises(AdwError) as caught:
                    adw_core.record_specification_package(
                        item, "Complete investigation and specification", "REQUEST-2",
                        state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                    )

                self.assertEqual("incomplete_specification", caught.exception.kind)
                self.assertIn("RED strategy", str(caught.exception))

    def test_lead_contract_does_not_stop_on_internal_workflow_results(self):
        skill_root = Path(__file__).parents[1]
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        lead = (skill_root.parents[1] / "agents" / "development-workflow-lead.md").read_text(encoding="utf-8")

        for contract in (skill, lead):
            self.assertIn("artifact", contract)
            self.assertIn("command", contract)
            self.assertIn("evidence", contract)
            self.assertIn("judge result", contract)
            self.assertIn("transition", contract)
            self.assertIn("generic `continue`", contract)
            self.assertIn("committed `BLOCKED`", contract)
            self.assertIn("committed `COMPLETE`", contract)
            self.assertIn("Do not invent a container user", contract)
            self.assertIn("observed command output", contract)
            self.assertIn("ticket-local `artifacts/**`", contract)
            self.assertIn("standalone-copy-trunk", contract)

    def test_director2_harness_contract_always_clean_builds_and_recreates_the_image(self):
        harness = (Path(__file__).parents[2] / "director2-harness-test" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("always run `./gradlew clean build -PdisableRyuk`", harness)
        self.assertIn("always run `./build-harness-mysql-image.sh` from the host", harness)
        self.assertNotIn("build-harness-mysql-image-jenkins.sh", harness)
        self.assertIn("Server-build Docker image:** must already exist locally", harness)
        self.assertIn("never builds, pulls, publishes, or replaces it", harness)
        self.assertNotIn("reused existing image", harness)
        self.assertNotIn("Rebuild only if needed", harness)

    def test_records_one_complete_human_readable_specification_package(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            self.write_complete_specification_package(item)

            result = adw_core.record_specification_package(
                item, "Complete AVOD-style investigation package", "REQUEST-2",
                state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
            )

            snapshot = read_consistent_snapshot(item)
            artifact = item / result["source_ref"]
            self.assertEqual(result["revision_id"], snapshot.state["current_revisions"]["specification"])
            self.assertTrue(artifact.is_file())
            self.assertEqual(result["fingerprint"], "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest())
            package = artifact.read_text(encoding="utf-8")
            for name in ("01-scope.md", "02-investigation.md", "03-roadmap.md", "04-code-guide.md", "specification.md"):
                self.assertIn("Document: `%s`" % name, package)
            self.assertIn("MediaContentBuildHelper.java:687", package)

    def test_specification_snapshot_includes_an_arbitrarily_named_text_ticket_source(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            self.write_complete_specification_package(item)
            source_name = "jira-AVOD-1.json"
            source_bytes = b'{"key":"AVOD-1","summary":"External Jira source"}\n'
            (item / source_name).write_bytes(source_bytes)

            result = adw_core.record_specification_package(
                item, "Complete package from Jira source", "REQUEST-2",
                state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
            )

            package = (item / result["source_ref"]).read_text(encoding="utf-8")
            self.assertIn("Source: `%s`" % source_name, package)
            self.assertIn("External Jira source", package)

    def test_specification_snapshot_binds_a_binary_ticket_source_by_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            self.write_complete_specification_package(item)
            source_bytes = b"%PDF-1.7\n\xffbinary-ticket\n"
            (item / "AVOD-1.pdf").write_bytes(source_bytes)

            result = adw_core.record_specification_package(
                item, "Complete package from binary ticket source", "REQUEST-2",
                state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
            )

            package = (item / result["source_ref"]).read_text(encoding="utf-8")
            self.assertIn("Source: `AVOD-1.pdf`", package)
            self.assertIn("sha256:" + hashlib.sha256(source_bytes).hexdigest(), package)

    def test_records_one_generated_change_revision_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)

            result = record_revision(
                item, "change", "git:abc123", "sha256:" + "b" * 64, "Add targeted behavior",
                "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

            snapshot = read_consistent_snapshot(item)
            revision_id = snapshot.state["current_revisions"]["change"]
            self.assertEqual(revision_id, result["revision_id"])
            self.assertTrue(revision_id.startswith("REV-"))
            self.assertEqual(1, len(snapshot.state["revision_history"]))
            self.assertEqual("change", snapshot.state["revision_history"][0]["domain"])
            self.assertEqual(2, snapshot.audit["sequence"])

    def test_director2_test_design_rejects_invented_container_execution_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            contract = (
                "# Scenario Verification Contract\n\n"
                "Capability: director2-harness-test\n"
                "The harness executes as jenkins, not root.\n"
                "run-harness-sidecar.sh -p -t 1 -j 2048 suite/dis/test/test-case.xml\n"
            ).encode("utf-8")
            path = item / "artifacts" / "test-design" / "contract.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(contract)

            with self.assertRaises(AdwError) as caught:
                record_revision(
                    item, "test_design", "artifacts/test-design/contract.md",
                    "sha256:" + hashlib.sha256(contract).hexdigest(), "Record test design",
                    "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("incomplete_test_design", caught.exception.kind)
            self.assertIn("container execution claim", str(caught.exception))

    def test_director2_test_design_rejects_malformed_harness_target(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            contract = (
                "# Scenario Verification Contract\n\n"
                "Capability: director2-harness-test\n"
                "run-harness-sidecar.sh -p -t 1 -j 2048 suite/dis/test-case.xml\n"
            ).encode("utf-8")
            path = item / "artifacts" / "test-design" / "contract.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(contract)

            with self.assertRaises(AdwError) as caught:
                record_revision(
                    item, "test_design", "artifacts/test-design/contract.md",
                    "sha256:" + hashlib.sha256(contract).hexdigest(), "Record test design",
                    "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("incomplete_test_design", caught.exception.kind)
            self.assertIn("harness target", str(caught.exception))

    def test_director2_test_design_accepts_a_capability_bound_harness_target(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            contract = (
                "# Scenario Verification Contract\n\n"
                "Capability: director2-harness-test\n"
                "run-harness-sidecar.sh -p -t 1 -j 2048 suite/dis/test/test-case.xml\n"
            ).encode("utf-8")
            path = item / "artifacts" / "test-design" / "contract.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(contract)

            result = record_revision(
                item, "test_design", "artifacts/test-design/contract.md",
                "sha256:" + hashlib.sha256(contract).hexdigest(), "Record test design",
                "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
            )

            self.assertEqual(result["revision_id"], read_consistent_snapshot(item).state["current_revisions"]["test_design"])

    def test_invalidates_only_evidence_bound_to_the_prior_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["current_revisions"]["change"] = "REV-OLD"
            evidence["evidence_index"] = [
                {"id": "E-CHANGE", "input_revisions": {"change": "REV-OLD"}, "validity_status": "current"},
                {"id": "E-SPEC", "input_revisions": {"specification": "REV-SPEC"}, "validity_status": "current"},
            ]
            write_genesis(item, state=state, evidence=evidence)
            snapshot = read_consistent_snapshot(item)

            record_revision(
                item, "change", "git:def456", "sha256:" + "c" * 64, "Correct behavior",
                "REQUEST-2", snapshot.audit["sequence"], snapshot.audit["head"], "lead/run-2",
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

            entries = {entry["id"]: entry for entry in read_consistent_snapshot(item).evidence["evidence_index"]}
            self.assertEqual("invalidated", entries["E-CHANGE"]["validity_status"])
            self.assertIn("REV-OLD", entries["E-CHANGE"]["invalidation_reason"])
            self.assertEqual("current", entries["E-SPEC"]["validity_status"])

    def test_rejects_an_unsafe_revision_source_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)

            with self.assertRaises(AdwError) as caught:
                record_revision(
                    item, "change", "/private/secret.diff", "sha256:" + "d" * 64, "Unsafe source",
                    "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("invalid_input", caught.exception.kind)
            self.assertEqual(1, read_consistent_snapshot(item).audit["sequence"])

    def test_requires_a_matching_immutable_snapshot_for_specification(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)

            with self.assertRaises(AdwError) as caught:
                record_revision(
                    item, "specification", "git:abc123", "sha256:" + "e" * 64, "Update specification",
                    "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("invalid_input", caught.exception.kind)

    def test_generic_revision_command_cannot_bypass_the_specification_package_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            snapshot_path = item / "artifacts" / "specification" / "approved.json"
            snapshot_path.parent.mkdir(parents=True)
            contents = b'{"approved":true}\n'
            snapshot_path.write_bytes(contents)
            fingerprint = "sha256:" + hashlib.sha256(contents).hexdigest()

            with self.assertRaises(AdwError) as caught:
                record_revision(
                    item, "specification", "artifacts/specification/approved.json", fingerprint, "Approve specification",
                    "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("invalid_input", caught.exception.kind)
            self.assertEqual(1, read_consistent_snapshot(item).audit["sequence"])

    def test_rejects_malformed_revision_history_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["revision_history"] = ["malformed"]
            state, evidence = write_genesis(item, state=state, evidence=evidence)

            with self.assertRaises(AdwError) as caught:
                record_revision(
                    item, "change", "git:abc123", "sha256:" + "f" * 64, "Change",
                    "REQUEST-2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("invalid_control_block", caught.exception.kind)
            self.assertEqual(1, ControlBlock.parse((item / "state.md").read_bytes()).value["audit"]["sequence"])


class WorkflowHardeningTests(unittest.TestCase):
    def test_gate_rejects_a_null_required_revision(self):
        artifact = b"{}\n"
        record = valid_support_record(
            "E-TEST-DESIGN", artifact, state="TEST_DESIGN",
            evidence_type="gate_decision", producer_role="lead_agent",
            revisions={"specification": "REV-SPEC", "test_design": None, "configuration": "REV-CONFIG"},
        )
        record.update({"gate": "test_design_pass", "decision": "test_design_accepted"})

        with self.assertRaises(AdwError) as caught:
            validate_evidence_record(
                record, "AVOD-1",
                {"specification": "REV-SPEC", "test_design": None, "change": None,
                 "configuration": "REV-CONFIG", "environment": None},
            )

        self.assertEqual("invalid_control_block", caught.exception.kind)

    def test_evidence_artifact_rejects_secret_like_material(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, _ = write_genesis(item)
            artifact = b"Authorization: Bearer should-never-be-recorded\n"
            record = valid_support_record("E-SECRET", artifact)
            record["artifact_ref"] = "artifacts/evidence/e-redaction.json"

            with self.assertRaises(AdwError) as caught:
                record_evidence(
                    item, record, artifact, lambda candidate: True,
                    "REQUEST-SECRET", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("unsafe_evidence", caught.exception.kind)
            self.assertFalse((item / record["artifact_ref"]).exists())

    def test_human_receipt_requires_natural_approval_request_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt_root = Path(temp, "receipts")
            claim = {"work_item": "AVOD-1", "decision": "specification_approved", "revision": "REV-SPEC", "role": "ticket_owner"}
            receipt = create_receipt(
                receipt_root, "human_approval", "ticket_owner", claim, canonical_json(claim),
                "session-human", "turn-human", "event-human", str(Path.cwd()),
            )
            proposal = {
                "work_item": "AVOD-1", "decision": "specification_approved", "producer_role": "ticket_owner",
                "producer_ref": "codex-local-human:session-human", "producer_proof_ref": receipt["ref"],
                "input_revisions": {"specification": "REV-SPEC"},
            }

            with self.assertRaises(AdwError) as caught:
                adw_receipts._verify_producer_receipt(receipt, proposal, canonical_json(claim))

            self.assertEqual("authority_required", caught.exception.kind)

    def test_judge_receipt_must_bind_revisions_and_findings(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt_root = Path(temp, "receipts")
            claim = {
                "work_item": "AVOD-1", "decision": "continue_to_local_qa", "state": "CODE_QUALITY_GATE",
                "result_status": "pass", "supports": ["E-TDD"], "input_revisions": {"change": "REV-OLD"},
                "findings": [],
            }
            receipt = create_receipt(
                receipt_root, "judge_output", "judge_agent", claim, canonical_json(claim),
                "session-judge", "turn-judge", "event-judge", str(Path.cwd()),
            )
            proposal = {
                "work_item": "AVOD-1", "decision": "continue_to_local_qa", "producer_role": "judge_agent",
                "producer_proof_ref": receipt["ref"], "state": "CODE_QUALITY_GATE", "result_status": "pass",
                "supports": ["E-TDD"], "input_revisions": {"change": "REV-CURRENT"},
                "findings": [{"id": "F-1", "severity": "high"}],
            }

            with self.assertRaises(AdwError) as caught:
                adw_receipts._verify_producer_receipt(receipt, proposal, canonical_json(claim))

            self.assertEqual("authority_required", caught.exception.kind)

    def test_local_qa_gate_cannot_advance_on_unrelated_support(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = valid_state(), valid_evidence()
            state["state"] = "LOWER_ENV_VERIFY"
            state["current_revisions"] = {domain: "REV-" + domain.upper() for domain in state["current_revisions"]}
            support_artifact = b'{"artifact":"not-local-qa"}\n'
            evidence["evidence_index"] = [valid_support_record(
                "E-UNRELATED", support_artifact, state="LOWER_ENV_VERIFY",
                revisions=copy.deepcopy(state["current_revisions"]), evidence_type="artifact_snapshot",
            )]
            state, _ = write_genesis(item, state=state, evidence=evidence)
            (item / "artifacts" / "evidence").mkdir(parents=True)
            (item / "artifacts" / "evidence" / "E-UNRELATED.json").write_bytes(support_artifact)
            gate_artifact = b'{"decision":"local_qa_accepted"}\n'
            gate = valid_support_record(
                "E-LOCAL-QA", gate_artifact, state="LOWER_ENV_VERIFY",
                revisions=copy.deepcopy(state["current_revisions"]), evidence_type="gate_decision", producer_role="lead_agent",
            )
            gate.update({"gate": "local_qa_pass", "decision": "local_qa_accepted", "supports": ["E-UNRELATED"]})
            record_evidence(
                item, gate, gate_artifact, lambda candidate: True,
                "REQUEST-LOCAL-QA", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
            )

            with self.assertRaises(AdwError) as caught:
                validate_transition(item, "MUTATION_GATE", None, "E-LOCAL-QA")

            self.assertEqual("invalid_transition", caught.exception.kind)

    def test_evidence_command_must_be_registered_in_the_current_test_design(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            repository = Path(temp, "director2-aws")
            repository.mkdir()
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, _ = write_genesis(item)

            with self.assertRaises(AdwError) as caught:
                run_evidence_command(
                    item, [sys.executable, "-c", "print('unregistered')"], repository,
                    "E-UNREGISTERED", "command:unregistered", [], [0],
                    "REQUEST-COMMAND", "lead/run-2", state["audit"]["sequence"], state["audit"]["head"],
                )

            self.assertEqual("invalid_input", caught.exception.kind)

    def test_director2_test_design_rejects_short_user_flag_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, _ = write_genesis(item)
            contract = (
                "# Scenario Verification Contract\n\n"
                "Capability: director2-harness-test\n"
                "docker exec -u root director2-aws-build bash -lc 'run-harness-sidecar.sh -p -t 1 -j 2048 suite/../test/test-case.xml'\n"
            ).encode("utf-8")
            path = item / "artifacts" / "test-design" / "unsafe-contract.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(contract)

            with self.assertRaises(AdwError) as caught:
                record_revision(
                    item, "test_design", "artifacts/test-design/unsafe-contract.md",
                    "sha256:" + hashlib.sha256(contract).hexdigest(), "Record test design",
                    "REQUEST-DIRECTOR2", state["audit"]["sequence"], state["audit"]["head"], "lead/run-2",
                )

            self.assertEqual("incomplete_test_design", caught.exception.kind)


class RecoveryTests(unittest.TestCase):
    def _crash_prepared_transaction(self, item, acquired):
        state, evidence = write_genesis(item)
        proposed_state = copy.deepcopy(state)
        proposed_state["owner"] = "lead/run-2"
        with self.assertRaises(InjectedCrash):
            commit_transaction(
                item, proposed_state, copy.deepcopy(evidence),
                expected_sequence=1, expected_head=state["audit"]["head"],
                transaction_id="TX-2", request_id="REQUEST-2", command="record-revision",
                safe_arguments={"domain": "change"}, lead_run_ref="lead/run-2",
                semantic_ids=["CHANGE-2"], intended_result={"revision_id": "CHANGE-2"},
                now=acquired, crash_at="after_replace:state.md",
            )
        return state

    def test_recovers_an_expired_prepared_transaction_to_its_journaled_base(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            self._crash_prepared_transaction(item, acquired)

            result = recover_work_item(
                item, "TX-2", "RECOVERY-2", "lead/recovery-2",
                now=acquired + timedelta(minutes=2),
            )
            repeated = recover_work_item(
                item, "TX-2", "RECOVERY-3", "lead/recovery-3",
                now=acquired + timedelta(minutes=3),
            )

            self.assertEqual("aborted", result["status"])
            self.assertEqual(result, repeated)
            self.assertEqual(1, read_consistent_snapshot(item).audit["sequence"])
            transaction = item / ".adw" / "transactions" / "2-TX-2"
            self.assertTrue((transaction / "abort.json").is_file())
            self.assertFalse((item / ".adw" / "write.lock").exists())

    def test_does_not_recover_a_prepared_transaction_before_its_write_lease_expires(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            self._crash_prepared_transaction(item, acquired)

            with self.assertRaises(AdwError) as caught:
                recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(seconds=30))

            self.assertEqual("busy", caught.exception.kind)
            self.assertTrue((item / ".adw" / "write.lock").is_dir())
            self.assertFalse((item / ".adw" / "transactions" / "2-TX-2" / "abort.json").exists())

    def test_refuses_to_rollback_a_prepared_transaction_when_its_write_lock_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            self._crash_prepared_transaction(item, acquired)
            lock = item / ".adw" / "write.lock"
            (lock / "owner.json").unlink()
            (lock / "owner.flock").unlink()
            lock.rmdir()

            with self.assertRaises(AdwError) as caught:
                recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))

            self.assertEqual("recovery_required", caught.exception.kind)
            self.assertFalse((item / ".adw" / "transactions" / "2-TX-2" / "abort.json").exists())

    def test_preserves_a_prepared_transaction_when_a_target_has_a_third_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            self._crash_prepared_transaction(item, acquired)
            (item / "state.md").write_bytes(control_bytes(valid_state(), b"\n# Untrusted edit\n"))

            with self.assertRaises(AdwError) as caught:
                recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))

            self.assertEqual("integrity_hold", caught.exception.kind)
            transaction = item / ".adw" / "transactions" / "2-TX-2"
            self.assertFalse((transaction / "abort.json").exists())
            self.assertTrue(any((transaction / "recovery-events").iterdir()))

    def test_finalizes_a_committed_transaction_with_an_expired_write_lock_without_a_new_sequence(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            proposed_state = copy.deepcopy(state)
            proposed_state["owner"] = "lead/run-2"
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            with self.assertRaises(InjectedCrash):
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2", command="record-revision",
                    safe_arguments={"domain": "change"}, lead_run_ref="lead/run-2",
                    semantic_ids=["CHANGE-2"], intended_result={"revision_id": "CHANGE-2"},
                    now=acquired, crash_at="after_commit_marker",
                )

            result = recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))
            repeated = recover_work_item(item, "TX-2", "RECOVERY-3", "lead/recovery-3", now=acquired + timedelta(minutes=3))

            self.assertEqual("committed", result["status"])
            self.assertEqual(result, repeated)
            self.assertEqual(2, read_consistent_snapshot(item).audit["sequence"])
            self.assertFalse((item / ".adw" / "write.lock").exists())

    def test_reclaims_an_expired_recovery_lock_before_resuming_prepared_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            state = self._crash_prepared_transaction(item, acquired)
            orphan = LeaseLock.acquire(
                item, "recovery", state["work_item"], "RECOVERY-OLD", "RECOVERY-OLD",
                state["audit"]["sequence"], state["audit"]["head"], "lead/recovery-old", 60,
                now=acquired + timedelta(minutes=2),
            )
            orphan.abandon()

            result = recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=4))

            self.assertEqual("aborted", result["status"])
            events = item / ".adw" / "transactions" / "2-TX-2" / "recovery-events"
            self.assertTrue(any(path.name.startswith("stale-recovery-") for path in events.iterdir()))

    def test_rejects_a_competing_fresh_recovery_lease_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            state = self._crash_prepared_transaction(item, acquired)
            transaction = item / ".adw" / "transactions" / "2-TX-2"
            owner = LeaseLock.acquire(
                item, "recovery", state["work_item"], "RECOVERY-HELD", "RECOVERY-HELD",
                state["audit"]["sequence"], state["audit"]["head"], "lead/recovery-held", 60,
                now=acquired + timedelta(minutes=2),
            )
            try:
                with self.assertRaises(AdwError) as caught:
                    recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))
                self.assertEqual("busy", caught.exception.kind)
                self.assertFalse((transaction / "abort.json").exists())
            finally:
                owner.release()

    def test_resumes_after_a_crash_that_preserved_the_stale_write_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            state = self._crash_prepared_transaction(item, acquired)
            transaction = item / ".adw" / "transactions" / "2-TX-2"
            claim = LeaseLock.claim_expired(item, "write", transaction / "recovery-events", now=acquired + timedelta(minutes=2))
            claim.close()
            orphan = LeaseLock.acquire(
                item, "recovery", state["work_item"], "RECOVERY-OLD", "RECOVERY-OLD",
                state["audit"]["sequence"], state["audit"]["head"], "lead/recovery-old", 60,
                now=acquired + timedelta(minutes=2),
            )
            orphan.abandon()

            result = recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=4))

            self.assertEqual("aborted", result["status"])
            self.assertTrue((transaction / "abort.json").is_file())

    def test_moves_a_published_uncommitted_artifact_to_the_recovery_area(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            proposed_state = copy.deepcopy(state)
            proposed_state["owner"] = "lead/run-2"
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            with self.assertRaises(InjectedCrash):
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2", command="record-revision",
                    safe_arguments={"domain": "change"}, lead_run_ref="lead/run-2",
                    semantic_ids=["CHANGE-2"], intended_result={"revision_id": "CHANGE-2"},
                    artifacts={"artifacts/proof.txt": b"proof"}, now=acquired,
                    crash_at="after_artifact:artifacts/proof.txt",
                )

            result = recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))

            transaction = item / ".adw" / "transactions" / "2-TX-2"
            self.assertEqual("aborted", result["status"])
            self.assertFalse((item / "artifacts" / "proof.txt").exists())
            self.assertEqual([b"proof"], [path.read_bytes() for path in (transaction / "orphaned-artifacts").iterdir()])

    def test_rejects_a_malformed_prepared_artifact_map_without_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            self._crash_prepared_transaction(item, acquired)
            transaction = item / ".adw" / "transactions" / "2-TX-2"
            manifest = json.loads((transaction / "manifest.json").read_text(encoding="utf-8"))
            manifest["artifacts"] = []
            (transaction / "manifest.json").write_bytes(canonical_json(manifest))

            with self.assertRaises(AdwError) as caught:
                recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))

            self.assertEqual("integrity_hold", caught.exception.kind)
            self.assertFalse((transaction / "abort.json").exists())

    def test_releases_a_matching_expired_write_lock_when_an_abort_is_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            state = self._crash_prepared_transaction(item, acquired)
            recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))
            stale = LeaseLock.acquire(
                item, "write", state["work_item"], "TX-2", "REQUEST-2",
                state["audit"]["sequence"], state["audit"]["head"], "lead/run-2", 60,
                now=acquired + timedelta(minutes=3),
            )
            stale.abandon()

            result = recover_work_item(item, "TX-2", "RECOVERY-3", "lead/recovery-3", now=acquired + timedelta(minutes=5))

            self.assertEqual("aborted", result["status"])
            self.assertFalse((item / ".adw" / "write.lock").exists())

    def test_rejects_a_staged_artifact_parent_substitution_without_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            proposed_state = copy.deepcopy(state)
            proposed_state["owner"] = "lead/run-2"
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            with self.assertRaises(InjectedCrash):
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2", command="record-revision",
                    safe_arguments={"domain": "change"}, lead_run_ref="lead/run-2",
                    semantic_ids=["CHANGE-2"], intended_result={"revision_id": "CHANGE-2"},
                    artifacts={"artifacts/proof.txt": b"proof"}, now=acquired,
                    crash_at="after_artifact:artifacts/proof.txt",
                )
            transaction = item / ".adw" / "transactions" / "2-TX-2"
            staged_artifacts = transaction / "staged" / "artifacts"
            outside = Path(temp, "outside-artifacts")
            os.rename(str(staged_artifacts), str(outside))
            staged_artifacts.symlink_to(outside, target_is_directory=True)

            with self.assertRaises(AdwError) as caught:
                recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))

            self.assertEqual("integrity_hold", caught.exception.kind)
            self.assertTrue((item / "artifacts" / "proof.txt").exists())
            self.assertFalse((transaction / "abort.json").exists())

    def test_rejects_a_tampered_commit_marker_without_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Path(temp, "AVOD-1")
            (item / ".adw" / "transactions").mkdir(parents=True)
            state, evidence = write_genesis(item)
            proposed_state = copy.deepcopy(state)
            proposed_state["owner"] = "lead/run-2"
            acquired = datetime(2026, 1, 2, tzinfo=timezone.utc)
            with self.assertRaises(InjectedCrash):
                commit_transaction(
                    item, proposed_state, copy.deepcopy(evidence),
                    expected_sequence=1, expected_head=state["audit"]["head"],
                    transaction_id="TX-2", request_id="REQUEST-2", command="record-revision",
                    safe_arguments={"domain": "change"}, lead_run_ref="lead/run-2",
                    semantic_ids=["CHANGE-2"], intended_result={"revision_id": "CHANGE-2"},
                    now=acquired, crash_at="after_commit_marker",
                )
            marker = item / ".adw" / "transactions" / "2-TX-2" / "commit.json"
            payload = json.loads(marker.read_text(encoding="utf-8"))
            payload["transaction_id"] = "TX-TAMPERED"
            marker.write_bytes(canonical_json(payload))

            with self.assertRaises(AdwError) as caught:
                recover_work_item(item, "TX-2", "RECOVERY-2", "lead/recovery-2", now=acquired + timedelta(minutes=2))

            self.assertEqual("integrity_hold", caught.exception.kind)
            self.assertFalse((item / ".adw" / "transactions" / "2-TX-2" / "abort.json").exists())


if __name__ == "__main__":
    unittest.main()
