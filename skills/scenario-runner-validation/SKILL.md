---
name: scenario-runner-validation
description: Independently reviews a docker-director2 acceptance scenario before deployment. Use when deciding whether scenario YAML is grounded in the ticket and repository sources, has safe and justified data behavior, needs the right deployed services/databases, and is ready for a live QA run. Does not author, repair, deploy, or run scenarios.
---

# Scenario Runner Validation

## Overview

Review scenario YAML as test code. A schema-valid YAML file is not an accepted
scenario.

## When to Use

Use this after an Engineer has authored a ticket scenario and before DEPLOY.
Review the actual YAML and source evidence independently. Do not edit the YAML,
invent a fixture, choose data setup, or deploy the environment.

## Read first

Open all of the following before reaching a verdict:

1. The accepted ticket specification and relevant investigation/code-guide.
   Also read the Lead's coverage ledger and direct Loop 1 GREEN evidence cited
   for any **LOOP 1 HARNESS** behavior.
2. The scenario YAML under review.
3. `scenarios/AUTHORING.md`, `scenarios/DESIGN.md`, and `scenarios/README.md`.
4. The closest applicable scenario anywhere under `scenarios/`, including
   ticket scenarios rather than only `scenarios/examples/`.
5. The actual code, fixture, or schema cited by any specific request, query,
   ID, date, setup, mutation, or cleanup action.

Do not accept an Engineer's summary as evidence.

Evidence may be composed across compatible sources. Require a source map that
collectively covers the domain relationships, any adapted test-value rule,
ownership, cleanup, and the complete precondition. Do not reject a value only
because it is not copied verbatim from the ticket fixture; reject it when no
existing source or pattern establishes its derivation.

## Review gates

All gates pass before DEPLOY.

Run data readiness fail-fast. First compare every YAML insert's explicit
columns with the closest repository fixture, then trace each inserted row into
the first production query that materializes it. Enumerate that query's inner
joins and filters before reviewing later stages. If any join lacks a witness,
return that defect immediately; do not bury it under an exhaustive review of
downstream optional dependencies.

Require a column-by-column disposition for every closest-fixture row:
**included**, or **omitted with schema and production-reader evidence that the
default/`NULL` is safe**. Also require columns introduced by current production
readers even if the fixture predates them. Any YAML column absent from this
accounting, or any accounted required column absent from the YAML, is an
incomplete-table defect and returns to SCENARIOS.

| Gate | Verify from evidence | Reject when |
|---|---|---|
| Ticket coverage | Every **LIVE** Given/When/Then maps to a tight YAML assertion; every **LOOP 1 HARNESS** behavior cites direct GREEN evidence for its exact approved contract | A behavior is unaccounted for, weakly asserted, or assigned to harness without exact GREEN evidence and a runner control unavailable live |
| Scenario form | Step kinds and request/query shapes follow a documented or existing pattern | A step or request shape is invented |
| Data readiness | Independently trace the complete request → async worker → source build → materialization → asserted-output path. For every stage, inspect the query and its consumer; verify every mandatory joined/referenced row and every returned field consumed without fallback maps to YAML setup and a precondition traversing the same relationship. Use schema DDL for legal row shape and production code/fixtures for required relationships and values. | Review stops at changed code; data is assumed; setup omits any downstream dependency or consumed field; a value lacks a derivation; or the precondition checks only primary-table counts while the real route has additional requirements |
| Mutation safety | Every mutation/cleanup has source-backed ownership and lifecycle evidence | A scenario deletes, resets, or restores data because it seems prudent |
| Deployment needs | Union actual operation paths into `--services` and `DB_DEPLOY_TYPE` | A required runtime service or local database is absent |
| Schema | Run `python3 schema_validate.py --file <path>` from `scenarios/` and read its output | The command fails or validates a different path |

For every production query in the traced path, enumerate its `INNER JOIN`s
and filtering predicates. Require a join witness for each one: the YAML setup
assigns both join-key values and a precondition starts from the scenario-owned
record and traverses that exact relationship. An assertion that the referenced
row exists separately is insufficient and must be returned to SCENARIOS.

For `contentSearch`, both `--services` and `DB_DEPLOY_TYPE` must include
`router,data1,data2`.

An always-run teardown is not by itself a runner blocker. First check whether
each cleanup SQL can require an exact persisted ownership marker with
`WHERE`/`EXISTS` or a same-database join. The marker must identify the specific
row being deleted, survive until its dependents are removed, and be deleted
last. Return unconditional fixed-ID cleanup to SCENARIOS for this repair. If a
required target has no marker or relationship that SQL can verify, identify
that exact target in the **RETURN TO SCENARIOS** verdict.
When the runner accepts arbitrary cleanup SQL, the next action is the
Engineer's YAML repair—not a runner change, human approval, disposable
database, or BLOCKED status. Independently derive this result; do not repeat a
prior state document's blocker claim.

## Verdict

Return one of:

- **ACCEPTED FOR DEPLOY** — every gate has direct evidence. Record the exact
  accepted YAML path and required deployment union.
- **RETURN TO SCENARIOS** — one or more gates lack evidence. State the exact
  unsupported YAML step, sources searched, and missing evidence; return it to
  the Engineer for investigation rather than asking the user to design the
  fixture. Do not propose invented data or a speculative repair.
- **RETURN TO SPECS** — the ticket behavior itself is ambiguous or the YAML
  would need to replace an approved requirement. A clear behavior already
  proved by exact Loop 1 GREEN harness evidence does not return to SPECS merely
  because the live runner lacks that harness control.

Schema validation alone never produces **ACCEPTED FOR DEPLOY**.

An asynchronous API response that only accepts or starts work is not proof the
work completed. Before accepting, require a `wait:` and downstream assertion
that expose processing failure; otherwise return the scenario for repair.

Pre-deploy review proves the scenario's data plan, not that local databases
already contain its data. A precondition assertion must prove the complete
input state needed by the tested behavior, not merely that setup commands ran
or that some related rows exist. When data must be created, the accepted YAML
carries that setup; the runner executes it only after DEPLOY has brought up the
required local databases.

## After deployment

This skill's review does not prove behavior. Independent QA runs the same
accepted path with `./run_scenarios.sh <path>` after DEPLOY, so its setup runs
against the deployed databases, then reads the runner's JUnit XML and
`report.html` directly. A live failure is evidence for investigation, not
permission to rewrite scenario assumptions during validation.

## Common Rationalizations

- "Schema validation passed" — it does not prove fixture completeness.
- "The API returned success" — an asynchronous start response does not prove
  downstream processing completed.

## Red Flags

- The precondition checks only rows inserted by the YAML, not production joins.
- A referenced row exists, but no setup value and precondition connect it to
  the scenario-owned row through the production join.
- Required related rows or selected fields have no source-backed values.
- The evidence has no stage-by-stage path from action entrypoint to assertion.

## Verification

- Every review gate has direct evidence, including the coverage ledger's exact
  Loop 1 GREEN evidence for any **LOOP 1 HARNESS** behavior.
- The schema command validated the exact YAML path.
- The verdict identifies the accepted path or the precise back-routing gap.
