---
{
  "work_item": "TICKET-ID",
  "repository": "repository-name",
  "state": "SPECIFY",
  "review_pass": null,
  "blocked_from_state": null,
  "blocked_from_review_pass": null,
  "resume_state": null,
  "resume_review_pass": null,
  "owner": "ticket-owner",
  "required_evidence_ids": [],
  "write_policy": {
    "policy_ref": "shared/local-write-policy",
    "policy_revision": null,
    "coordination_mode": "local_single_host",
    "lock_lease_seconds": 60,
    "transaction_schema": 1
  },
  "audit": {
    "sequence": 0,
    "head": null,
    "last_transaction_id": null,
    "last_request_id": null
  },
  "current_revisions": {
    "specification": null,
    "test_design": null,
    "change": null,
    "configuration": null,
    "environment": null
  },
  "revision_history": [],
  "gate_evidence": {
    "specification_approval": null,
    "test_design_pass": null,
    "tdd_pass": null,
    "first_review": null,
    "local_qa_pass": null,
    "mutation_decision": null,
    "final_review": null
  },
  "transition_history": [],
  "loop_policy": {
    "policy_ref": "shared/loop-policy",
    "policy_revision": null,
    "max_attempts_per_root_cause": 3,
    "max_review_correction_loops": 5,
    "max_extension_units_per_decision": 1,
    "max_extension_decisions_per_scope": 1
  },
  "blocker_ids": [],
  "exception_ids": []
}
---

# Delivery State: [Ticket ID — Title]

The strict JSON Control Block is owned by the workflow CLI after initialization. Do not hand-edit it; keep the Markdown below human-readable and consistent with the CLI-recorded fields.

## Current State

`[SPECIFY | TEST_DESIGN | TDD | CODE_QUALITY_GATE | LOWER_ENV_VERIFY | MUTATION_GATE | DELIVERY_GATE | COMPLETE | BLOCKED]`

- If blocked, origin: `[state]`
- If blocked, resume target: `[state]`

## Current Objective

[What must be proved or completed before this state can pass.]

## Current Owner

[Lead agent | specification agent | test-design agent | TDD agent | judge | developer/ticket owner]

## Required Evidence

- [ ] [Evidence item]

## Committed Audit Snapshot

- Sequence/head: [sequence / sha256]
- Last transaction/request: [TX-ID / request ID]
- Write-policy reference/revision: [reference / revision]
- Integrity status: [consistent/busy/recovery_required/integrity_hold and reason]

## Current Revision Vector

| Domain | Current revision ID | Safe source/fingerprint | Last change reason |
|---|---|---|---|
| specification | [revision/null] | [reference/fingerprint] | [reason] |
| test_design | [revision/null] | [reference/fingerprint] | [reason] |
| change | [revision/null] | [reference/fingerprint] | [reason] |
| configuration | [revision/null] | [reference/fingerprint] | [reason] |
| environment | [revision/null] | [reference/fingerprint] | [reason] |

## Current Gate Decisions

| Gate | Decision evidence ID | Decision | Producer/ref/proof | Usability |
|---|---|---|---|---|
| [gate] | [E-ID/null] | [decision] | [authorized role/ref/proof] | [current/stale/missing and reason] |

## Revision History

| Audit sequence / transaction | Time | Domain | Prior revision | New revision | Safe source/fingerprint | Reason | Recorded by/proof |
|---|---|---|---|---|---|---|---|
| [sequence/TX-ID] | [UTC time] | [domain] | [revision/null] | [revision] | [safe ref/fingerprint] | [reason] | [lead run/proof] |

## Next Action

[Exact next action, owner, and configured command when applicable.]

## Loop Accounting

- Policy reference/revision: [reference / revision]
- Derived review correction loops: [N / effective limit]
- Review-loop extension decisions: [none / E-IDs and units]

| Root-cause ID | Relation / parents | Status | Distinct attempt IDs | Derived attempts / effective limit | Extension decisions |
|---|---|---|---|---|---|
| [RC-ID] | [new/refine/reopen/split/merge; parents] | [open/resolved/replaced/exhausted] | [E-ATTEMPT-IDs] | [N/limit] | [none/E-IDs and units] |

## Blockers

| ID | Category | Origin state/pass | Blocker decision/support IDs | Failed/missing criterion | Owner / exact action | Resume state/pass, resolution IDs, validation |
|---|---|---|---|---|---|---|
| [BLOCK-ID] | [category] | [state/pass-or-null] | [decision E-ID/support E-IDs] | [criterion] | [owner/action] | [state/pass; resolution E-IDs; validation] |

## Transition History

| Audit sequence / transaction | Time | Kind | From state/pass | To state/pass | Decision evidence ID | Correction loop / attempt IDs | Reason, supporting evidence, next action |
|---|---|---|---|---|---|---|---|
| [sequence/TX-ID] | [time] | [advance/correct/block/resume] | [state/pass-or-null] | [state/pass-or-null] | [E-DECISION-ID] | [sequence or null / E-ATTEMPT-IDs] | [reason, E-IDs, owner/action] |

## Approved Exceptions

| ID | Scope/scenario | Decision evidence / producer proof | Revision dependencies | Reason | Remaining risk | Follow-up/expiry |
|---|---|---|---|---|---|---|
| [EXCEPTION-ID] | [scope] | [E-ID / producer proof] | [domain=revision] | [reason] | [risk] | [owner/date] |
