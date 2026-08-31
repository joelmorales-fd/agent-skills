# Review: [Ticket ID — Title]

Append one complete gate-assessment record for every `CODE_QUALITY_GATE` or `DELIVERY_GATE` attempt. Never overwrite a prior outcome or finding. Each decision references a uniquely named immutable safe snapshot/artifact; this mutable `review.md` file is the human-readable findings and decision history, not the gate artifact by itself.

## Review Pass

`[FIRST_CODE_REVIEW | FINAL_EVIDENCE_REVIEW]`

## Audit Snapshot Reviewed

- Sequence/head: [sequence / sha256]
- Transaction/snapshot token: [TX-ID / token]
- Consistency validation: [pass/fail and evidence]

## Input Revision Vector

| Domain | Revision reviewed |
|---|---|
| specification | [revision] |
| test_design | [revision] |
| change | [revision] |
| configuration | [revision] |
| environment | [revision/null for CODE_QUALITY_GATE] |

## Inputs Reviewed

- [ ] Approved specification and Gherkin scenarios
- [ ] Test design and traceability
- [ ] Tests, code, and diff
- [ ] Actual configured command output
- [ ] Current gate decision IDs and their supporting-evidence chains
- [ ] Local-environment QA evidence (`DELIVERY_GATE`)
- [ ] Mutation evidence when required (`DELIVERY_GATE`)

## Evidence Integrity

- [ ] Every claimed result has inspectable command output, report, diff, or observable scenario evidence.
- [ ] No skipped, flaky, timed-out, or infrastructure-failed result is counted as pass.
- [ ] Local scenario target matches the selected local topology.
- [ ] Evidence contains no exposed secret value.

## Findings

| ID | Origin | Severity | Root-cause ID/relation | Changed location | Finding/classification evidence IDs | Affected scenario/rule | Required correction | Attempt/resolution evidence IDs | Status |
|---|---|---|---|---|---|---|---|---|---|
| [ID] | [introduced/worsened/pre-existing] | [critical/high/medium/low] | [RC-ID/relation] | [path] | [E-IDs] | [scenario] | [correction] | [E-IDs/none] | [open/resolved/follow-up] |

## Gate Results

- Quality gate: [pass/fail]
- Process gate: [pass/fail]
- Scenario traceability: [pass/fail]
- Local-environment QA gate (`DELIVERY_GATE`): [pass/fail/not applicable]
- Mutation gate (`DELIVERY_GATE`): [pass/fail/not required]

## Outcome

`[continue_to_local_qa | return_to_tdd | return_to_test_design | return_to_specify | blocked | approved]`

- Decision evidence ID: [E-ID]
- Judge producer reference: [configured judge run ID]
- Judge producer proof reference: [runtime-issued run reference]
- Supporting evidence IDs: [E-IDs inspected]
- Decision artifact/integrity reference: [safe ref]
- Supersedes decision evidence: [none/E-ID]
- Decision committed at audit sequence/transaction: [sequence/TX-ID]

## Approval Rationale

[Evidence-backed reason for the decision, including every required final-gate result.]

## Loop Record

- Loop-policy reference/revision: [reference/revision]
- Root-cause lineage and distinct attempts: [RC-ID; parents; E-ATTEMPT-IDs; N/effective limit]
- Derived work-item review correction loops: [sequence and submitted attempt IDs; N/effective limit]
- Bounded extension decisions: [none / E-ID, scope, units, use]
- If blocked: [exhausted dimension, accounting evidence, clear question for responsible developer]
