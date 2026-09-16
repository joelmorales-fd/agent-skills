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
3. Find one closest applicable scenario under `scenarios/` with a targeted
   search and use it for runner syntax; do not inventory every scenario.
4. The source fixture, selected code route, schemas, and named request
   definitions needed by the scenario. Download the complete current schema
   set to a temporary evidence directory with this skill's
   `scripts/download-dbschemas.sh` before writing; do not modify a product
   repository.

Do not replace an exact ticket contract with a generalized live-data check.
Do not ask the user to design fixture rows. Produce a concrete candidate from
the repository evidence.

A harness fixture is authoritative evidence for its hierarchy and domain
relationships even when those rows are not deployed. Translate the rows needed
by the selected feature query into scenario setup using the current schemas and
its immediate consumer. Do not request an "authoritative live fixture contract"
or a deployed copy of the fixture when those repository sources establish the
required state.

## Build the data contract first

Work as an engineer, not as an exhaustive proof search:

1. Map each Lead-classified **LIVE** behavior to the real feature action and
   assertion. Do not recreate a **LOOP 1 HARNESS** behavior in YAML.
2. Read the feature query and its immediate consumer. List only the tables,
   joins, filters, and returned fields that can reject the test row or determine
   the asserted value.
3. For each listed table, inspect the current DDL and one closest valid row.
   Prefer an existing scenario or ticket harness fixture. When authorized and
   reachable, a read-only `SELECT` from the lower database may supply another
   valid row shape; it is optional evidence, never a prerequisite.
4. Create deterministic, ticket-owned source rows with the required columns and
   relationships. Use database-relative times for active, expired, or future
   windows. Do not insert the expected derived output.
5. Add one precondition query that joins the created rows through the same keys
   and filters as the feature query.
6. Write the candidate YAML immediately, run schema validation, and repair only
   the concrete table, field, join, or YAML error that fails.

For a broad publish/build operation, the selected route is only:

- the base-content query that decides whether the scenario-owned object can be
  materialized; and
- the ticket-specific query/computation that produces the asserted behavior.

Do not trace every optional enrichment builder invoked by the publisher. Use a
valid base row as the template for ordinary fields, then add the ticket-specific
relationships and values. Deeper path review belongs to the independent
scenario validator and returns one concrete repair if needed.

Extract evidence with this skill's bounded helper; do not invent `sed`, `awk`,
or broad `rg` pipelines over schemas and fixtures:

```bash
python3 <skill-directory>/scripts/extract-db-evidence.py ddl <schema.sql> <table>
python3 <skill-directory>/scripts/extract-db-evidence.py fixture <fixture.xml> <table> --id <ticket-id>
```

Run the fixture command once per selected table and repeat `--id` for related
ticket IDs. The helper fails instead of flooding context when the result is too
broad. Never `cat` a large fixture or schema.

Use this compact ledger while authoring:

| Table/row | Required columns and relationships | Example source | YAML setup/precondition |
|---|---|---|---|

Schema-required columns plus fields used by the selected query/consumer must be
present. Other fixture columns may use schema defaults unless the selected path
reads them. Do not search unrelated readers, sibling fixtures, or every
caller/callee to prove that an unused column is safe.

Repository fixtures establish domain relationships; existing scenarios
establish runner syntax and lifecycle patterns. Read-only live rows can provide
examples, but the YAML must create deterministic state and cannot depend on the
sample still existing.

Missing live data, an unavailable read-only database, or a harness-only fixture
does not block authoring. Return without YAML only when the accepted behavior or
API action is ambiguous enough that choosing one would change the specification.
Name that ambiguity and route it to SPECS. All missing test data is Engineer
work: derive it from the fixture, selected production query, schema, or one valid
row example and put it in the YAML.

This skill has no `BLOCKED` outcome. It returns either a schema-valid candidate
YAML or `RETURN TO SPECS` for one concrete behavior/API ambiguity.

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
6. Assert every **LIVE** Given/When/Then using exact values or tight response
   checks.
7. Restore captured values or remove only records whose ownership is proven.

Top-level teardown runs even when setup fails. Therefore, an absence check for
a fixed ID does not establish safe cleanup: teardown must delete through a
persisted scenario-owned marker/relationship, or setup must capture and later
restore the prior state. Never unconditionally delete a chosen ID merely
because an earlier step was expected to prove it unused. Verify cleanup for
the complete materialized state, not only the feature-specific output table.

The ownership condition may live in the SQL itself; it does not require a new
runner feature. Use `DELETE ... WHERE ... AND EXISTS (...)` (or an equivalent
join) so each deletion requires an exact marker on the row being deleted or a
relationship to that row in the same database. Insert the marker with the
owned row, use a ticket-specific value, and delete it last. Gate each record
independently: one global marker is unsafe when another fixed ID can collide.
If the runner always invokes teardown, repair unconditional deletes this way
before returning the candidate YAML.

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

- "The insert succeeded, so the fixture is complete" — the selected feature
  query and matching joined precondition must also accept the rows.
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
- mapping from each **LIVE** ticket behavior to its assertion;
- compact table/row ledger and source citations;
- schema artifact/version and selected production route;
- `--services` and `DB_DEPLOY_TYPE` unions;
- schema command output;
- `RETURN TO SPECS` ambiguity, if any; otherwise none.

Before returning, reread the YAML rather than the planning notes and compare
its inserts and precondition join with the compact ledger. If they differ,
repair the YAML and rerun schema validation.

Do not deploy, run `run_scenarios.sh`, approve the YAML, or reinterpret the
ticket. Stop for independent `scenario-runner-validation`.
