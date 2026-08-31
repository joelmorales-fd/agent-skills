# Agentic Development Workflow Verification

This directory is the verification home for the Agentic Development Workflow runtime. Runtime code remains under `scripts/`; tests and test-strength checks remain here and ship with the skill.

## Logic Flow

```text
strict Control Blocks
  -> schema, policy, lineage, and path validation
  -> held advisory lease
  -> idempotency and committed-chain validation
  -> before/staged journal preparation
  -> immutable artifact publication and full-file CAS replacement
  -> target verification
  -> immutable commit-marker publication
  -> consistent reader accepts only the complete committed chain
  -> revision and host-verified evidence mutations remain atomic
  -> gate validation checks recursive support and current revisions
  -> transition tokens bind the exact approved movement
  -> lead correction routing atomically invalidates stale downstream gates and revisions
  -> correction attempts and corrected code-quality submissions are derived from history
  -> init uses only bundled assets and creates an audit-bound ticket-local runtime configuration
  -> init creates the complete AVOD-style specification package
  -> record-specification rejects shallow investigation and snapshots the complete package
  -> status exposes a safe, human-readable ticket snapshot
  -> approval preflight binds the exact declaration scope before a simple revision-bound human reply
  -> record-approval atomically records the human decision without an agent proposal file
  -> recover exposes transaction-table rollback/finalization only after its lease proofs pass
  -> host hooks issue immutable approval-request, human, lead-call, and judge receipts
  -> lead-owned exit gates use one exact host-bound record-lead-decision command
  -> public evidence recording binds producer receipt, exact lead call, artifact, and current revisions
  -> real command capture records actual argv, exit, output, and pass/fail without a shell
```

Every failed or ambiguous check stops at its boundary. No reader treats a prepared, mixed, tampered, or unsupported-filesystem snapshot as committed.

## Normal Tests

Run from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 skills/agentic-development-workflow/tests/test_adw_core.py -v
```

The suite covers strict parsing, schema and lineage rules, containment, advisory lock ownership, stale-lock preservation, idempotency, transaction staging, races, crash boundaries, rollback, immutable artifacts, terminal markers, hash-chain reads, tamper detection, arbitrary-name local ticket-source adoption, self-contained bundled-template initialization, audit-bound ticket-local runtime configuration, AVOD-style package validation, pre-existing-work/RED-strategy consistency, lead continuation instructions, atomic specification snapshots, generic-revision bypass prevention, revision recording/invalidation, prepared natural-language approval, receipt reuse after restart, receipt-verified public evidence recording, host-bound lead decisions and correction/transition calls, exact test-design command registry enforcement, recursive direct-support validation, every forward gate, concrete `CODE_QUALITY_GATE`/`DELIVERY_GATE` states, atomic lead correction routing with stale-approval invalidation, BLOCKED/resume, derived three-attempt root-cause limits, derived five-submission code-quality correction limits, public transition commands, and transaction-table recovery. Bounded human loop extensions, Control Block restoration, and authenticated secret-safe runner execution remain unavailable.

## Mutation Tests

Run from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 skills/agentic-development-workflow/tests/run_mutation_tests.py
```

The runner first requires the complete normal suite to pass. It then copies the runtime and tests into a temporary directory, applies each named mutation from `mutation_cases.json`, and runs only the tests assigned to detect that mutation. It never edits the real source.

- `killed`: the selected test detected the deliberately broken invariant.
- `survived`: a real test gap for this curated safety mutation; the command fails.
- `invalid_case`: the source changed and the mutation target is no longer exact; update the case only after reviewing the invariant.

This is a targeted safety gate, not a broad mutation score. Add a third-party mutation engine only if the runtime grows beyond one focused module and broader survivor discovery becomes worth the extra tooling.

## Invariant Map

| Safety boundary | Representative normal tests | Mutation probe |
| --- | --- | --- |
| Lock/path containment | `LeaseLockTests`, `PathContainmentTests`, journal symlink retry check | `lock-directory-symlink`, `stale-claim-work-item-symlink`, `journal-file-no-follow` |
| Immutable abort/commit evidence | `TransactionCommitTests`, `ConsistentReadTests` | `abort-recovery-hash-binding`, `commit-record-time-binding`, `committed-outcome-binding` |
| No overwrite of concurrent human edits | `test_conflict_after_first_replace_rolls_back_without_overwriting_human_edit` | `pre-replace-full-file-cas` |
| Artifact containment and substitution safety | nested-parent and post-validation substitution tests | `artifact-parent-symlink`, `publication-directory-chain-no-follow` |
| File-descriptor cleanup on failure | post-validation substitution resource-count assertion | `partial-publication-descriptor-cleanup` |
| Partial immutable publication rollback | injected post-link verification failure | `post-link-artifact-rollback-tracking` |
| Complete audit history | `test_commit_rejects_a_base_without_a_complete_committed_chain` | `committed-chain-completeness` |
| Ticket-source adoption | `InitAndStatusTests` arbitrary-name and partial-directory checks | `ticket-first-intake-shape` |
| Self-contained initialization | bundled-template, generated runtime-configuration, and configuration-tamper checks | `bundled-template-source`, `per-ticket-runtime-configuration`, `runtime-configuration-genesis-binding` |
| Real specification investigation | `RevisionTests` package/template/grounding and pre-existing-work RED-strategy checks | `specification-generic-revision-bypass`, `specification-template-completion`, `specification-investigation-grounding`, `specification-pre-existing-work-red-strategy` |
| Lead continuation boundary | `RevisionTests.test_lead_contract_does_not_stop_on_internal_workflow_results` | instruction contract; no runtime branch |
| Recovery ownership and retry | `RecoveryTests` expired/held/missing/write-preserved/recovery-lock cases | `prepared-recovery-write-lock-required`, `recovery-lock-expired-takeover` |
| Recovered immutable artifacts | `RecoveryTests.test_moves_a_published_uncommitted_artifact_to_the_recovery_area` | `recovery-staged-artifact-path` |
| Host evidence authority | receipt tamper/reuse and public CLI receipt tests | `evidence-host-authority-required`, `receipt-integrity-binding`, `receipt-private-permissions`, `lead-call-exact-argv-binding` |
| Natural approval freshness | preflight, restart reuse, and changed-specification rejection tests | `natural-approval-current-snapshot-binding` |
| Workflow approval scope and recording | unchanged declaration, generic-declaration isolation, and proposal-free recording tests | `record-approval-subcommand-binding` |
| Real command evidence | actual pass/fail and secret-output tests | `command-actual-exit-status`, `command-secret-output-rejection` |
| Recursive gate support | `TransitionValidationTests.test_forward_gate_cannot_convert_failed_support_to_pass` | `forward-gate-failed-support` |
| Lead-owned gate authority | lead decision positive/negative tests | `lead-decision-gate-ownership`, `lead-decision-subcommand-binding` |
| TDD RED/GREEN authority | RED/GREEN order plus current-change binding tests | `tdd-lead-decision-red-green-binding`, `tdd-lead-decision-evidence-order`, `tdd-lead-decision-requires-change-revision`, `tdd-green-evidence-binds-current-change` |
| Director2 harness test design | `RevisionTests` invalid container-claim and harness-target tests | `director2-test-design-container-claim`, `director2-test-design-harness-target` |
| Correction and quality-gate budgets | correction-attempt and corrected code-quality submission tests | `correction-attempt-lineage-budget`, `corrected-review-submission-accounting-required`, `review-correction-loop-budget` |
| Material specification correction | `CliTests.test_route_correction_returns_to_specify_and_invalidates_old_approval` | `correction-clears-stale-gates` |

## Adding or Changing Logic

1. Write the smallest failing normal test for the intended invariant.
2. Change the runtime and make the complete normal suite pass.
3. For a safety-critical condition, add or update one exact mutation case that disables or reverses it.
4. Run the mutation gate and require every curated mutation to be killed.
5. Review each survivor as a concrete missing assertion; do not approve from a score alone.
