---
name: scenario-runner-grounding
description: Grounds one drafted docker-director2 ticket scenario against the deployed local databases — resolves the real ids and data, finalizes the inserts, preconditions, and teardown, and runs schema validation. Use during the SCENARIO GROUND stage, after DEPLOY. Does not deploy or run scenarios.
---

# Scenario Runner Grounding

## Overview

Ground one drafted ticket scenario against the lower environment.
Resolve the real ids and data the draft left as placeholders, finalize the
setup inserts, the precondition, the assertions, and the teardown, then run
schema validation.

## When to Use

Use this in the SCENARIO GROUND stage, after DEPLOY has brought the lower
environment up. Read the draft, resolve its placeholders against the deployed
databases, write the finished YAML, run schema validation, report, and stop.

## Build the data contract first

Work as an engineer, not as an exhaustive proof search:

1. Map each behavior that must be proven in the deployed environment to its
   real feature action and assertion. Do not recreate in YAML a behavior that
   loop 1 already proved with unit tests.
2. Read the feature query and its immediate consumer. List only the tables,
   joins, filters, and returned fields that can reject the test row or determine
   the asserted value.
3. For each listed table, inspect the current DDL and one closest valid row.
   Prefer an existing scenario or the ticket's preloaded test rows. When authorized and
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
relationships and values. Deeper path review belongs to VALIDATE, not to this
pass.

Extract evidence with this skill's bounded helper; do not invent `sed`, `awk`,
or broad `rg` pipelines over schemas and preloaded row-set files:

```bash
python3 <skill-directory>/scripts/extract-db-evidence.py ddl <schema.sql> <table>
python3 <skill-directory>/scripts/extract-db-evidence.py rows <rows.xml> <table> --id <ticket-id>
```

Run the `rows` command once per selected table and repeat `--id` for related
ticket IDs. The helper fails instead of flooding context when the result is too
broad. Never `cat` a large preloaded row-set file or schema.

Use this compact table while authoring:

| Table/row | Required columns and relationships | Example source | YAML setup/precondition |
|---|---|---|---|

Schema-required columns plus fields used by the selected query/consumer must be
present. Other preloaded columns may use schema defaults unless the selected
path reads them. Do not search unrelated readers, sibling preloaded row sets, or
every caller/callee to prove that an unused column is safe.

The repository's preloaded rows establish domain relationships; existing
scenarios establish runner syntax and lifecycle patterns. Read-only rows from
the lower database can provide examples, but the YAML must create deterministic
state and cannot depend on the sample still existing.

Missing data in the deployed environment, an unavailable read-only database, or
preloaded rows that exist only in the harness do not block grounding. Return
without YAML only when the accepted behavior or API action is ambiguous enough
that choosing one would change the specification. Name that ambiguity and route
it to SPECS. All missing test data is Engineer work: derive it from the
preloaded rows, selected production query, schema, or one valid row example and
put it in the YAML.

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
6. Assert every Given/When/Then that must be proven in the deployed
   environment, using exact values or precise response checks.
7. Restore captured values or remove only records whose ownership is proven.

Top-level teardown runs even when setup fails. Therefore, an absence check for
a fixed ID does not establish safe cleanup: teardown must delete through a
persisted scenario-owned marker/relationship, or setup must capture and later
restore the prior state. Never unconditionally delete a chosen ID merely
because an earlier step was expected to prove it unused. Verify cleanup for
the complete materialized state, not only the feature-specific output table.

The ownership condition may be expressed in the SQL itself; it does not require a new
runner feature. Use `DELETE ... WHERE ... AND EXISTS (...)` (or an equivalent
join) so each deletion requires an exact marker on the row being deleted or a
relationship to that row in the same database. Insert the marker with the
owned row, use a ticket-specific value, and delete it last. Gate each record
independently: one global marker is unsafe when another fixed ID can collide.
If the runner always invokes teardown, repair unconditional deletes this way
before returning the candidate YAML.

Apply the canonical `only_on_env`/`skip_on_env` guard to every mutating SQL,
API, Redis, or Kafka step, including teardown.

Use actual local schemas; preloaded rows are evidence, not drop-in SQL.
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

- "The insert succeeded, so the test data is complete" — the selected feature
  query and matching joined precondition must also accept the rows.
- "The schema defines the relationship" — DDL proves legal structure; code
  and preloaded rows prove the runtime relationship and values.

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
- mapping from each ticket behavior proven in the deployed environment to its
  assertion;
- the compact row table and source citations;
- schema artifact/version and selected production route;
- `--services` and `DB_DEPLOY_TYPE` unions;
- schema command output;
- `RETURN TO SPECS` ambiguity, if any; otherwise none.

Before returning, reread the YAML rather than the planning notes and compare
its inserts and precondition join with the compact row table. If they differ,
repair the YAML and rerun schema validation.

Do not deploy, run `run_scenarios.sh`, approve the YAML, or reinterpret the
ticket. Hand the grounded scenario to VALIDATE.
