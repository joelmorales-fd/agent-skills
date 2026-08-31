---
name: agentic-development-workflow
description: Leads one real software ticket through specification, test design, TDD, independent review, local verification, mutation analysis, and evidence-backed completion. Use when a user asks to start, continue, resume, inspect, or run the Agentic Development Workflow for a ticket.
---

# Agentic Development Workflow

## Overview

Operate one ticket through this evidence-gated state machine:

```text
SPECIFY -> TEST_DESIGN -> TDD -> CODE_QUALITY_GATE
        -> LOWER_ENV_VERIFY -> MUTATION_GATE -> DELIVERY_GATE -> COMPLETE
```

A failure returns to the smallest corrective state. `BLOCKED` preserves the origin and exact action needed to resume. The responsible developer/ticket owner approves the completed specification; the independent judge approves the review gates and final result.

One ticket directory is the source of truth:

```text
<delivery-root>/<ticket-id>/
  <optional-original-ticket-source>
  state.md
  01-scope.md
  02-investigation.md
  03-roadmap.md
  04-code-guide.md
  specification.md
  evidence.md
  review.md
  completion.md
  artifacts/
  .adw/
    runtime-configuration.json
```

The lead owns state, evidence acceptance, configured command execution, and transitions. Specialists update only their assigned document/code area. The judge reviews but never fixes, starts environments, deploys, or transitions state.

## Codex Runtime Ownership

In Codex, the primary agent in the active user conversation is the running lead. Load this skill as the lead's rules; do not treat the skill, a hook, the CLI, or an `agents/*.md` file as a background controller.

The primary lead may delegate bounded work to specialist subagents, but it retains the current state, evidence judgment, next-action decision, and transition authority. Hooks only issue host receipts. The CLI only validates and records mechanical facts. Neither component monitors or advances the workflow independently.

## When to Use

Use this skill to start, resume, inspect, or lead one real workflow ticket. Do not use it as a generic test runner or to bypass a repository's own profile, command governance, or credential boundary.

## Non-Negotiable Rules

- Read a fresh committed `status` before accepting a handoff, recording evidence, or transitioning.
- Never use the documentation repository as a template, configuration, or policy input. Initialization uses only assets packaged with this skill and creates the ticket-local runtime configuration itself.
- Never hand-edit either JSON Control Block, `.adw/`, an audit record, evidence status, or transition history.
- Never request specification approval from a summary. `01-scope.md`, `02-investigation.md`, `03-roadmap.md`, `04-code-guide.md`, and `specification.md` must form one validated AVOD-style package.
- Before approval, inspect the fresh ticket-relevant repository diff and record whether implementation or tests already exist plus the selected safe RED strategy. Never manufacture RED by reversing the active worktree.
- Do not code until the specification is human-approved and TEST_DESIGN proves every Gherkin scenario is testable.
- A green agent summary is not evidence. Record the actual command result or a host receipt.
- Tests should use real supported interfaces—API, harness, Kafka, database, browser, or runner—as selected by the feature-specific test design. Do not fake data when a supported real interface can establish it.
- Run only repository-profile commands selected by the approved Scenario Verification Contract.
- For `director2-aws` harness evidence, apply `director2-harness-test`. Do not invent a container user, user-switch flag, or readiness prerequisite; it must be selected by the test design or shown in observed command output.
- Never place credentials, sessions, tokens, cookies, authorization headers, secret paths, or raw login output in prompts, arguments, work-item files, or evidence.
- Authenticated execution remains `BLOCKED` until its repository-specific secret-safe wrapper is verified.
- Critical/high change-related findings block. Correctness, security, reliability, testability, or approved-scenario medium findings block by default. Low findings may be follow-ups. Pre-existing findings do not block unless the change worsens them.
- Maximum defaults are three material attempts per stable root cause and five corrected-review submissions. Exhaustion enters `BLOCKED`; do not rename a cause to reset its budget.

## Start or Resume a Ticket

1. Resolve `scripts/adw.py` relative to this `SKILL.md` and use its absolute path for every command.
2. Identify only the ticket ID, repository, responsible owner, and delivery root. Do not ask the owner for a runtime-configuration or template path.
3. Ensure the canonical directory is absent, or contains only one original local ticket-source file. Preserve a local source byte-for-byte under its original safe filename; never rename it to `ticket.txt`. A Jira issue or another external system may instead be the source—record its stable reference and relevant content in the generated package without inventing a local filename requirement.
4. Initialize once with `init`. It loads the skill's bundled templates and policy, then creates an audit-bound `.adw/runtime-configuration.json` for this ticket. Runtime/request references must be unique safe correlation values; they are not producer proof.
5. Run `status --format json`. If it reports `busy`, wait. If it reports recovery/integrity failure, stop gate work and follow explicit recovery.
6. Read the current state document and only the shared/state/repository guidance needed for that state. In `SPECIFY`, read [the AVOD-style specification package contract](references/specification-package.md) before investigating.

Example shape:

```bash
python3 <absolute-skill-path>/scripts/adw.py init <ticket-id> \
  --repository <repository> --owner <ticket-owner> \
  --delivery-root <delivery-root> \
  --request-id <unique-request-id> --lead-run-ref <safe-lead-reference> --format json

python3 <absolute-skill-path>/scripts/adw.py status <ticket-id> \
  --delivery-root <configured-root> --format json
```

## Lead Control Loop

Repeat exactly one current-state action at a time, continuously within the same turn:

1. Read `status` and retain its audit sequence/head.
2. Identify the one missing exit criterion.
3. Investigate or issue one bounded specialist assignment with exact inputs, output area, and acceptance criteria.
4. Validate the returned artifact against the same revisions/snapshot.
5. Record a revision or evidence through the CLI.
6. Re-read `status` because every committed mutation changes the sequence/head.
7. When the gate is complete, call `validate-transition`; pass its exact token unchanged to `transition` using the same snapshot.
8. On failure, record the criterion/root cause and route to the smallest corrective state. Do not continue optimistically.

After every action, return immediately to step 1. “One action at a time” does not mean one action per user turn. A progress message is a checkpoint, not a terminal response. Yield to the user only for required investigation input, approval of the exact specification revision, an explicit exception or committed `BLOCKED` owner action, or committed `COMPLETE`. Never ask the user to type a generic `continue` to cross an internal gate.

An artifact, command result, evidence record, judge result, correction route, or committed transition is input to the next loop iteration—not a stopping condition. Choose among configured safe actions without asking the owner to orchestrate. When no configured safe action can satisfy the current criterion, record the exact blocker and transition to `BLOCKED` before yielding.

If later investigation proves an approved specification or test design materially wrong, do not ask the owner to approve the working edits and do not remain in the later state. From a fresh status snapshot, run the lead-owned correction command:

```bash
python3 <absolute-skill-path>/scripts/adw.py route-correction <ticket-id> \
  --delivery-root <configured-root> --target-state SPECIFY \
  --reason <what-the-new-investigation-disproved> \
  --next-action <smallest-corrective-action> --owner <responsible-owner> \
  --request-id <unique-request-id> --expected-sequence <n> \
  --expected-head <sha256:...> --lead-run-ref <safe-lead-reference> --format json
```

The command atomically records the lead decision, returns to the selected earlier state, clears downstream revisions and gate pointers, and invalidates the old approval when returning to `SPECIFY`. Then correct and record the package, run approval preflight, and ask for approval of the new immutable revision.

## State Contracts

### SPECIFY

Follow [the AVOD-style specification package contract](references/specification-package.md). The internal sequence is ticket intake, scope clarification, initial research, questions, deeper repository investigation, roadmap, code guide, specification synthesis, package validation, and human approval. Investigation quotes real code with current file paths and line numbers, traces the behavior end to end, identifies reuse, and records open questions; a few conclusion bullets are not an investigation.

Feature-specific applications, databases, dependencies, and test topology remain investigation results—not global defaults. Ask one useful question at a time when human input is required, and repeat research after answers expose new uncertainty.

Before recording the package, inspect fresh repository status and the ticket-relevant diff. Complete the `Existing Work and TDD Entry` section in `01-scope.md`:

- `normal-red-first`: no ticket implementation or tests exist; add and run the approved test before production changes.
- `current-failing-test`: a ticket test already exists and its actual current failure can provide RED.
- `isolated-clean-baseline`: ticket work exists, and an explicitly configured isolated baseline can prove the test fails without mutating the active worktree.
- `blocked`: no safe RED path exists.

Do not use retrospective claims or temporarily reverse, stash, reset, restore, or remove active ticket files to manufacture RED.

After all five package documents are complete, run `record-specification`. It validates the package, creates one immutable human-readable snapshot, and records its revision atomically. The generic `record-revision --domain specification` path is not allowed.

Before asking the human, ensure the active write declaration already lists the exact ticket documents and implementation/test files approved by `04-code-guide.md`. Do not add a proposal file or broaden the declaration for approval recording. Then run the approval preflight against a fresh status snapshot:

```bash
python3 <absolute-skill-path>/scripts/adw.py prepare-approval <ticket-id> \
  --delivery-root <configured-root> --role ticket_owner \
  --expected-sequence <n> --expected-head <sha256:...> --format text
```

Run this receipt-bearing command alone in one tool call; do not chain it after `status` or another command. If its fresh host receipt is missing, rerun it alone before considering a restart. Preflight adds only the canonical ticket-local `artifacts/**` namespace for later immutable workflow snapshots, then binds the declaration's exact task and file-list fingerprint to this workflow, ticket, immutable revision, and approval request and sets it unapproved. After it succeeds, show the exact immutable snapshot and ask the owner to reply `I approve`. That reply captures the human receipt and authorizes the unchanged matching declaration, including those workflow-owned artifacts; it is also the workflow-specific equivalent of `proceed`. It never authorizes a new implementation or test file, a path outside the ticket, or another process's declaration.

After approval capture, read fresh status and record it atomically without creating an agent-written proposal file:

```bash
python3 <absolute-skill-path>/scripts/adw.py record-approval <ticket-id> \
  --delivery-root <configured-root> --role ticket_owner \
  --expected-sequence <n> --expected-head <sha256:...> --format json
```

Run `record-approval` alone so the host issues the exact lead-call receipt. Never manufacture either receipt. After a restart, run preflight again: it reuses an already captured current approval and the owner is not asked twice. Only the prepared natural-language reply `I approve` is accepted; structured approval text is not a workflow interface.

### TEST_DESIGN

For every approved Gherkin scenario, document the behavior boundary, setup/preconditions, action, externally observable result, smallest trustworthy test levels, command/capability IDs, expected outputs, evidence, local topology if needed, credential boundary, cleanup, and failure route. When deeper investigation changes the approved behavior or implementation contract, use `route-correction --target-state SPECIFY`; this invalidates the old approval before the package is revised and approved again. Enter `BLOCKED` when no safe required capability exists.

The specification approval already authorizes the ticket-local `artifacts/**` namespace for immutable workflow snapshots. Never pause to request a generic `proceed` for a test-design snapshot or another internal workflow artifact. A separately configured isolated baseline still needs its narrow, explicit authorization because it is outside the ticket directory.

The Scenario Verification Contract must contain exactly one strict JSON command registry. Each real evidence command has one stable ID, exact argv, expected exits, and timeout. For example:

```adw-command-registry
{"commands":{"harness-red":{"argv":["/absolute/path/run-harness-sidecar.sh","-p","-t","6","-j","3000","/dis/test/test-example.xml"],"expected_exit_codes":[1],"timeout_seconds":900}}}
```

The lead may execute only an exact entry from the current immutable test-design snapshot. This is command governance, not a place for credentials or shell text.

When the complete test design is current and validated, record the lead-owned decision through its exact host-bound command. For `director2-aws`, a harness contract must name `director2-harness-test`, use a real `suite/<suite>/test/<file>.xml` target, and must not prescribe a container user, `--user`, `non-root`, or `standalone-copy-trunk` behavior:

```bash
python3 <absolute-skill-path>/scripts/adw.py record-lead-decision <ticket-id> \
  --delivery-root <configured-root> --id <evidence-id> \
  --gate test_design_pass --expected-sequence <n> --expected-head <sha256:...> \
  --format json
```

Run the command alone in one tool call. Then read fresh status, validate and commit `TEST_DESIGN -> TDD`, read status again, and start the first TDD action in the same turn. Do not return a final response merely because the test design or its acceptance evidence was recorded.

### TDD

Give the implementation agent only the approved specification/test design and affected repository context. Execute the recorded RED strategy before production edits: capture the current failing test, use the configured isolated clean baseline, or enter committed `BLOCKED`. On the normal path, add the approved test and run it RED before changing production code. Then require the smallest implementation, GREEN evidence, build/static checks selected by the design, and scenario traceability. A failing actual command stays in TDD; weak test design returns to TEST_DESIGN.

After production edits, record the `change` revision before capturing GREEN: every GREEN command must bind to that current revision. The lead records `tdd_pass` only with actual command evidence: pass each failing RED command ID with `--historical-support` and each later passing GREEN command ID with `--supports`. The CLI rejects missing, overlapping, stale, non-command, out-of-order, or change-unbound RED/GREEN proof. If a prior TDD gate must be corrected while still in `TDD`, record a new decision with a new ID and `--supersedes <prior-tdd-evidence-id>`; do not edit or delete evidence history. After recording the decision, transition to `CODE_QUALITY_GATE` and continue the loop in the same turn.

### CODE_QUALITY_GATE

Give an independent judge the approved specification, test design, diff, tests, and actual artifacts. The judge performs the code and test quality gate and reports structured change-focused findings with severity, location, evidence, affected criterion/scenario, correction, and status. Its receipt result contains the exact current `input_revisions`, direct supports, and a `findings` list. Every finding has `id`, `severity` (`critical|high|medium|low`), `classification`, `blocking`, `location`, `criterion`, `evidence`, and `status`; the receipt cannot be reused after a revision changes. Blocking findings return to the smallest corrective state.

### LOWER_ENV_VERIFY

Use the local environment as QA verification, not a separate QA environment. Validate only the topology selected during TEST_DESIGN. For Director2 Docker work, verify Docker/Compose, at least 12 GB memory and 7 CPUs, the selected `environments.env` configuration, required applications/databases/dependencies, readiness, target, scenario behavior, and cleanup before claiming pass. A running container alone is not readiness. Authenticated runner work requires the secret-safe wrapper.

### MUTATION_GATE

Use the existing mutation-testing capability only when meaningful changed logic needs proof that ordinary tests would catch a realistic fault. Record the decision, baseline, exact scope, mutations, killed/surviving results, and follow-up. A meaningful survivor returns to TDD.

### DELIVERY_GATE and COMPLETE

The independent judge rechecks the current five-domain revision vector, the code-quality decision, all blocking-finding resolutions, actual local verification, mutation decision/result, exceptions, and complete direct-support chain. Only its evidence-backed `approved` delivery decision permits `COMPLETE`. Completion is a delivery-ready handoff, not a production-deployment claim.

## Recording Real Results

Specification approval uses `record-approval`, which constructs and records its evidence atomically from the exact human and lead-call receipts; it never requires a proposal file. Other human- or judge-owned decisions use `record-evidence` with a strict evidence proposal whose producer receipt matches its role, decision, artifact, work item, and current revisions. Lead-owned exit gates use `record-lead-decision`; the Codex `PreToolUse` hook binds a lead-call receipt to that exact invocation and the CLI creates the gate artifact atomically. Run receipt-bearing commands alone in their tool calls. Missing, stale, tampered, mismatched, or reused receipts fail closed.

For a real non-secret command selected by TEST_DESIGN, use:

```bash
python3 <absolute-skill-path>/scripts/adw.py run-evidence-command <ticket-id> \
  --delivery-root <configured-root> --id <evidence-id> \
  --cwd <absolute-repository-root> --source-ref command:<approved-command-id> \
  --supports <supporting-evidence-id> --expected-sequence <n> --expected-head <sha256:...> \
  --format json -- <executable> <arg> ...
```

The command runs without a shell. Its argv, expected exits, and timeout must exactly equal the current registry entry. Its real argv, working directory, exit code, expected exits, stdout, and stderr become an immutable evidence artifact. The actual exit code decides pass/fail. Secret-like or oversized output is rejected instead of stored.

## Common Rationalizations

- “The agent says the test passed.” Require the actual command artifact.
- “The specification is obvious.” Complete investigation, Gherkin, and explicit human approval.
- “This command probably works here.” Use only the selected repository-profile capability.
- “The finding is old.” Record it as pre-existing unless the change introduced or worsened it.
- “One more retry is harmless.” Enforce the root-cause and review-loop budgets.

## Red Flags

- Coding begins while the specification or test design gate is open.
- A receipt/reference is typed by an agent instead of returned by the host.
- A test replaces a supported real API/event/database interaction with fabricated state.
- A judge fixes code, executes the environment, or approves from summaries.
- Command arguments/output contain credentials or session material.
- Docker starts before the feature-specific topology/readiness contract is complete.

## Verification of This Skill

Before installing an update, require all of these:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 <absolute-skill-path>/tests/test_adw_core.py -v
PYTHONDONTWRITEBYTECODE=1 python3 <absolute-skill-path>/tests/run_mutation_tests.py
bash <plugin-root>/hooks/codex-workflow-receipts-test.sh
```

The normal suite must have zero failures/skips, every curated safety mutation must be killed, and the hook test must capture approval preflight, lead-decision, command/evidence, human, and judge receipt paths. Plugin hooks load at session start, so test an installed update in a new Codex session.
