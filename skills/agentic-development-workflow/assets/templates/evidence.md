---
{
  "work_item": "TICKET-ID",
  "audit": {
    "sequence": 0,
    "head": null,
    "last_transaction_id": null,
    "last_request_id": null
  },
  "evidence_index": []
}
---

# Evidence: [Ticket ID — Title]

Record only actual, attributable results. Do not include secret values or raw unredacted reports.

The strict JSON Control Block is a safe evidence index owned by the workflow CLI after initialization. Do not hand-edit it; keep the human-readable evidence records below consistent with the CLI-recorded index.

## Evidence Index Entry Shape

The CLI appends entries with this shape. Result fields are immutable; later validity changes retain the original result.

```json
{
  "id": "E-TDD-001",
  "type": "command_result",
  "work_item": "TICKET-ID",
  "state": "TDD",
  "review_pass": null,
  "observed_at": "2026-01-01T00:00:00Z",
  "recorded_at": "2026-01-01T00:00:01Z",
  "audit_sequence": 2,
  "transaction_id": "TX-EXAMPLE",
  "request_id": "REQUEST-EXAMPLE",
  "expires_at": null,
  "result_status": "fail",
  "validity_status": "current",
  "producer_role": "qa_tool",
  "producer_ref": "command-id/run-id",
  "producer_proof_ref": "runtime-issued-producer-reference",
  "recorded_by": "lead-agent/run-id",
  "decision": null,
  "scenario_ids": ["SCENARIO-1"],
  "source_ref": "command:configured-command-id",
  "artifact_ref": "artifacts/E-TDD-001-redacted.txt",
  "integrity_ref": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "input_revisions": {
    "specification": "SPEC-REVISION-ID",
    "test_design": "TEST-DESIGN-REVISION-ID",
    "change": "CHANGE-REVISION-ID",
    "configuration": "CONFIGURATION-REVISION-ID",
    "environment": "ENVIRONMENT-REVISION-ID"
  },
  "supports": [],
  "historical_supports": [],
  "revision_transition": null,
  "root_cause_ids": [],
  "root_cause_relation": null,
  "parent_root_cause_ids": [],
  "resolved_root_cause_ids": [],
  "loop_extension": null,
  "supersedes": [],
  "invalidation_reason": null
}
```

## Command Results

| ID | Time | State/pass | Type | Producer/ref/proof | Scenario/rule | Source and integrity | Expected / actual result | Result | Validity | Input revisions |
|---|---|---|---|---|---|---|---|---|---|---|
| [E-ID] | [UTC time] | [state/pass] | [type] | [role/ref/proof] | [scenario/rule] | [source; artifact; integrity] | [expected / concise actual] | [pass/fail/blocked/unstable/not_run/not_required] | [current/superseded/invalidated] | [domain=revision] |

## Committed Audit Binding

- Current sequence/head: [sequence / sha256]
- Current transaction/request: [TX-ID / request ID]
- Integrity status: [consistent/busy/recovery_required/integrity_hold and reason]

## Decision Evidence

| ID | Decision | Authorized producer/ref/proof | State/pass | Supports | Revision vector | Artifact/integrity | Result/validity | Supersedes |
|---|---|---|---|---|---|---|---|---|
| [E-DECISION-ID] | [configured decision] | [role/ref/proof] | [state/pass] | [E-IDs] | [domain=revision] | [safe ref/integrity] | [pass/current] | [prior decision ID/none] |

## TDD Red-Green Evidence

| Scenario/rule | RED evidence / baseline change revision | GREEN evidence / current change revision | TDD-cycle evidence ID and revision transition | Refactor recheck evidence |
|---|---|---|---|---|
| [scenario] | [historical E-ID / revision] | [current E-ID / revision] | [E-ID / from -> to] | [current E-ID/not required] |

## Root-Cause and Correction-Attempt Evidence

| Evidence ID | Type/decision | Root-cause ID(s) | Relation/parents | Failed criterion and source evidence | Planned material correction / outcome evidence | Policy revision | Derived attempt number(s) |
|---|---|---|---|---|---|---|---|
| [E-ID] | [root_cause_record/root_cause_identified or correction_attempt/correction_attempt_started] | [RC-IDs] | [new/refine/reopen/split/merge; parents] | [criterion/E-IDs] | [plan or outcome E-IDs] | [revision] | [RC-ID=N] |

## Loop-Budget Extension Evidence

| Decision evidence ID | Human producer/proof | Blocker ID | Scope | Added units | Policy/revision binding | Consumption/status |
|---|---|---|---|---|---|---|
| [E-ID] | [developer/ticket owner / proof] | [BLOCK-ID] | [root_cause:RC-ID or work_item_review] | [bounded positive integer] | [policy and dependent revisions] | [derived units used/remaining or invalidated] |

## Local-Environment QA Verification

| ID | Scenario | Selected local topology | Configuration fingerprint | Readiness result | Observable check | Result |
|---|---|---|---|---|---|---|
| [E-LOCAL-QA-ID] | [scenario] | [applications/databases/dependencies] | [non-secret revision/fingerprint] | [result] | [check] | [pass/fail/blocked] |

## Scenario Execution Evidence

| ID | Scenario | Runner/harness command | Target validation | Report location | Cleanup result | Status |
|---|---|---|---|---|---|---|
| [E-SCENARIO-ID] | [scenario] | [configured command] | [local target confirmed] | [redacted location] | [pass/fail/not required] | [pass/fail/blocked] |

## Mutation Decision

- Underlying mutation evidence ID: [E-MUTATION-ID]
- Lead `mutation_accepted` decision evidence ID: [E-DECISION-ID]
- Producer/ref/proof and artifact integrity: [values]
- Input revision dependencies: [domain=revision]
- Question: [what changed logic must tests protect]
- Required: [yes/no and reason]
- Scope: [target]
- Baseline: [pass/fail]
- Tooling: [configured/missing/unstable]
- Outcome: [useful signal/useful with noise/not worth it]
- Next action: [one concrete action]

## Mutation Survivors

| Survivor | Classification | Rationale | Follow-up |
|---|---|---|---|
| [mutant] | [real_gap/equivalent_or_low_value/tooling_or_environment_noise/needs_manual_inspection] | [why] | [action] |

## Supersession and Invalidation History

| Time | Evidence ID | Prior validity | New validity | Replacement/revision | Reason | Recorded by |
|---|---|---|---|---|---|---|
| [UTC time] | [E-ID] | [current] | [superseded/invalidated] | [new E-ID or domain revision] | [reason] | [lead/run] |
