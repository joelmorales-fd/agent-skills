---
name: scenario-runner-authoring
description: Authors or rewrites one docker-director2 ticket scenario from accepted ticket evidence and repository sources. Use during the SCENARIOS stage when YAML must establish deterministic test data and assertions before independent review. Does not approve, deploy, or run scenarios.
---

# Scenario Runner Authoring

## Overview

Create one review-ready scenario YAML. Do not depend on accidental data in the
lower environment.

## When to Use

Use this in `lean-scenario-acceptance`'s SCENARIOS stage. Write the YAML under
`scenarios/tickets/<TICKET-ID>/`, run its schema check, report the result, and
stop. `scenario-runner-validation` independently decides whether it may enter
DEPLOY.

## Read before writing

Read all of these directly:

1. The accepted `specification.md`, relevant investigation/code-guide, and
   real code diff.
2. `scenarios/AUTHORING.md`, `scenarios/DESIGN.md`, and `scenarios/README.md`.
3. The closest applicable scenarios anywhere under `scenarios/`, including
   ticket directories.
4. The actual source fixtures, code routes, schemas, and named request
   definitions needed by the scenario. Download the complete current schema
   set to a temporary evidence directory with this skill's
   `scripts/download-dbschemas.sh` before writing; do not modify a product
   repository.

Do not replace an exact ticket contract with a generalized live-data check.
Do not ask the user to design fixture rows before completing this source
search and producing a concrete candidate or explaining why each candidate
is unsupported.

## Build the data contract first

Start with the rows the YAML will create. For each inserted source table,
compare its explicit column list with the closest repository fixture row, then
trace that row into the first production query that builds the runtime object.
Resolve every inner join and filter there before investigating later stages.
Do not let a broad end-to-end search postpone this first materialization gate.

For each inserted table, build this complete row ledger from the closest
fixture before writing SQL:

| Fixture column | Scenario value/derivation | Production use | Decision |
|---|---|---|---|

Every fixture column must be marked **included** or **omitted with evidence**.
Add any column required by current production code even when the older fixture
does not contain it. An omission is valid only when the schema and every
production reader on the executed path prove the default or `NULL` is safe;
shorter SQL is not evidence. Generate the YAML column list and values directly
from this ledger, then compare them back to it. Any unexplained difference
means the table is incomplete and blocks authoring.

Build the scenario from the verified contract, not by copying an existing YAML
and patching whichever failure is currently visible. Existing scenarios supply
runner syntax and lifecycle patterns; ticket fixtures and production code
supply this scenario's data.

Complete these construction gates in order before writing YAML:

1. **Behavior:** map every accepted Given/When/Then to the real action and a
   downstream assertion.
2. **Source rows:** list every row the action needs, including join keys,
   filtered fields, and fields consumed without fallback. Give each value a
   repository source or derivation.
3. **Materialization:** prove every production inner join with a connected
   join witness rooted at the scenario's row.
4. **Ownership:** define how each mutation is uniquely owned and how every
   source and derived row is restored or removed even after partial failure.
5. **Execution:** derive services, databases, asynchronous waits, and
   environment guards from the actual route.

An unresolved cell blocks YAML generation. Do not emit a partial candidate as
review-ready.

For every test precondition, record:

| Condition | Source and derivation | Runtime action | Proof before feature action | Ownership/restoration | Services and DBs |
|---|---|---|---|---|---|

Trace each feature action end to end: request handler, queued/asynchronous
worker, source-object build, propagation/materialization, and asserted output.
Do not stop at the changed method or the feature-specific query. Before
writing YAML, complete this table for every executed stage:

| Runtime stage and caller | Query/read | Mandatory joins/references | Returned fields consumed without a fallback | YAML setup | Matching precondition proof |
|---|---|---|---|---|---|

Follow callers and callees until the value asserted by the scenario is
produced. For every database result, inspect both the query and its consumer:
an inner join requires the related row, and a field read without a default
requires a semantically valid value even when DDL supplies a legal default.
The YAML must create or prove every row and field in this dependency closure,
and its precondition must traverse the same relationships. Counts over only
the scenario's primary tables do not prove readiness when any downstream
stage has additional requirements.

For each production query reached by the action, enumerate every `INNER JOIN`
and filtering predicate. Each join needs a **join witness** in the YAML: setup
must assign both join-key values, and one precondition query must start from the
scenario-owned record and successfully traverse that exact relationship. A
separate assertion that the referenced row exists is not a join witness. Before
returning, compare the setup and preconditions against the enumeration; any
unwitnessed join or predicate makes the scenario not review-ready.

Use schema DDL to verify table names, columns, constraints, and legal insert
shapes. Use production queries and source fixtures to determine which related
rows and values are required. Schema existence alone does not prove a complete
fixture.

Use one data path per condition:

- **Provisioned:** repository evidence proves DEPLOY supplies the required
  state. Discover it and assert the complete state before the feature action.
- **Scenario-created:** otherwise, express source-backed `INSERT`/`UPDATE` or
  supported API setup in the YAML, then assert the complete state before the
  feature action.

A discovery query is not proof that matching data will exist. `SELECT ...
LIMIT 1` without a provisioning source is not an acceptable data plan.

Evidence may be composed across compatible sources. A ticket fixture can
establish domain relationships while an existing scenario establishes the
local test-value, time-window, ownership, and restoration pattern. Record the
source and derivation for each adapted value. Never call a record
scenario-owned merely because its ID was chosen for the scenario.

Historical fixture timestamps describe the required active, expired, or
future relationship; they do not require the live runner to reproduce the
fixture's wall clock. Preserve that relationship with source-side timestamps
derived from the database clock, then assert the resulting values. Missing
live rows or the absence of a harness-fixture loader is not a SPECS blocker:
use the repository schemas and fixture relationships to author the required
source-side `INSERT`/`UPDATE` setup in YAML. Capture and restore pre-existing
rows; delete only rows the scenario actually inserted.

The authoring result is invalid if it keeps a discovery-only candidate,
requests generalized live-data approval, or asks a human for fixture rows
solely because no matching row currently exists. If the accepted behavior and
repository sources define the state, construct that state and hand the YAML to
independent validation.

## Author the YAML

Order stateful scenarios as follows:

1. Capture original state before modifying existing records.
2. Create or update the complete source-side state required by the real code
   route. Do not insert the expected derived result merely to make the
   assertion pass.
3. Assert the complete data precondition: required relationships, types,
   flags, time window, and other fields used by the route.
4. Execute the real feature action.
5. Poll asynchronous output with `wait:` when needed.
6. Assert every accepted Given/When/Then using exact values or tight response
   checks.
7. Restore captured values or remove only records whose ownership is proven.

Top-level teardown runs even when setup fails. Therefore, an absence check for
a fixed ID does not establish safe cleanup: teardown must delete through a
persisted scenario-owned marker/relationship, or setup must capture and later
restore the prior state. Never unconditionally delete a chosen ID merely
because an earlier step was expected to prove it unused. Verify cleanup for
the complete materialized state, not only the feature-specific output table.

Apply the canonical `only_on_env`/`skip_on_env` guard to every mutating SQL,
API, Redis, or Kafka step, including teardown.

Use actual local schemas; harness fixtures are evidence, not drop-in SQL.
Follow established scenario request and mutation patterns instead of
inventing runner behavior.

## Schema downloader

The skill carries its own non-mutating copy of the established schema download
mechanism. It never installs packages. The caller must already have `curl`,
`zstd`, `tar`, `awk`, and `find`. With no artifact argument it downloads the
complete verified set: CIS, data1, data2, Hadoop, LS, main/router, and
promocode schemas.

```bash
# Download every Director2 schema artifact.
bash <skill-directory>/scripts/download-dbschemas.sh <temporary-output-directory>

# Download only the schema needed for the current route.
bash <skill-directory>/scripts/download-dbschemas.sh <temporary-output-directory> cis_schema
```

Read the downloaded SQL as evidence and cite its artifact/version from the
script's JSON output. Do not copy generated SQL into the scenario repository.

For `contentSearch`, both the service union and local DB union include
`router,data1,data2`. A source publish through
`disMediaCorePublishStream*` also includes `CIS` where its source data lives.

## Common Rationalizations

- "The insert succeeded, so the fixture is complete" — only the end-to-end
  production dependency closure and matching precondition prove that.
- "The schema defines the relationship" — DDL proves legal structure; code
  and fixtures prove the runtime relationship and values.

## Red Flags

- Setup covers fewer joins than the production read.
- A reference row is proved to exist, but the scenario-owned row never assigns
  the foreign/join key that connects to it.
- Analysis stops at the changed method instead of the asserted output.
- A selected field is consumed without fallback but omitted from setup proof.
- A publish/start response is the only proof for asynchronous behavior.
- Schema SQL is written into a product repository.

## Verification

From `scenarios/`, run and read:

```bash
python3 schema_validate.py --file <path>
```

Return:

- exact YAML path;
- mapping from each ticket behavior to its assertion;
- completed data contract and source citations;
- schema artifact/version and production dependency closure;
- `--services` and `DB_DEPLOY_TYPE` unions;
- schema command output;
- unresolved evidence gaps, if any.

Before returning, reread the YAML rather than the planning notes and perform
the same fail-fast source-row comparison and join-witness check against what
was actually written. If the YAML differs from the completed contract, repair
it and rerun schema validation.

Do not deploy, run `run_scenarios.sh`, approve the YAML, or reinterpret the
ticket. Stop for independent `scenario-runner-validation`.
