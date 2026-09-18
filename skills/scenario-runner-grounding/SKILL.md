---
name: scenario-runner-grounding
description: Grounds one drafted docker-director2 ticket scenario against the deployed local databases — resolves the real ids and data, finalizes the inserts, preconditions, and teardown, runs schema validation, then runs the scenario against the deployed system until it passes. Use during the SCENARIO GROUND stage, after DEPLOY. Does not deploy or render the QA verdict.
---

# Scenario Runner Grounding

## Overview

Ground one drafted ticket scenario against the lower environment.
Resolve the real ids and data the draft left as placeholders, finalize the
setup inserts, the precondition, the assertions, and the teardown, run schema
validation, then run the scenario against the deployed system until it passes.

## When to Use

Use this in the SCENARIO GROUND stage, after DEPLOY has brought the lower
environment up. Read the draft, resolve its placeholders against the deployed
databases, write the finished YAML, run schema validation, run the scenario
until it passes, report, and stop.

## Build the data contract first

Work as an engineer, not as an exhaustive proof search:

1. Map each behavior that must be proven in the deployed environment to its
   real feature action and assertion. Do not recreate in YAML a behavior that
   loop 1 already proved with unit tests.
2. Read the feature query and its immediate consumer. List only the tables,
   joins, filters, and returned fields that can reject the test row or determine
   the asserted value.
3. For each table the route reads, inspect the current DDL and query the deployed
   database for the real rows the chosen `contentId`s already have. Querying the
   deployed database is how you find valid data — required, not optional.
4. Do not create everything — the deployed databases already hold `contentId`s
   that are valid for what the scenario wants. `SELECT` for the `contentId`s that
   already qualify, or the closest to what we want, and use them; they already
   carry every joined row. Insert or update only the rows that the chosen `contentId`s still need to qualify
   for the scenario. Do not insert the expected derived output.
5. Write the candidate YAML immediately, run schema validation, and repair only
   the concrete table, field, join, or YAML error that fails.

For a broad publish/build operation, the selected route is only:

- the base-content query that decides whether the record the scenario asserts on
  can be materialized; and
- the ticket-specific query/computation that produces the asserted behavior.

Do not trace every optional enrichment builder invoked by the publisher. Reuse a
real, already-valid base row for ordinary fields, then add or adjust only the
ticket-specific relationships and values it still lacks. Deeper path review
belongs to VALIDATE, not to this pass.

Extract schema evidence with this skill's bounded helper; do not invent `sed`,
`awk`, or broad `rg` pipelines over schemas:

```bash
python3 <skill-directory>/scripts/extract-db-evidence.py ddl <schema.sql> <table>
```

Use this compact table while authoring:

| Table/row | Required columns and relationships | Example source | YAML setup/precondition |
|---|---|---|---|

Schema-required columns plus fields used by the selected query or consumer must
be present on the chosen content. When you must insert a row, its other columns
may take schema defaults unless the selected path reads them.

This skill has no `BLOCKED` outcome. It returns either a scenario that ran clean
end to end against the deployed system, or `RETURN TO SPECS` for one concrete
behavior/API ambiguity.

## Author the YAML

Order stateful scenarios as follows:

1. Capture original state before modifying existing records.
2. Reuse the `contentId`s the data contract chose, and insert or update only
   what they still lack to qualify for the real code route. Do not build the
   source-side hierarchy from scratch, and do not insert the expected derived
   result merely to make the assertion pass.
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
because an earlier step was expected to prove it unused. Clean up exactly what
this scenario inserted or updated — do not inspect or trace tables the scenario
itself never wrote to.

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


## Run it clean

Schema validation proves the YAML's shape, not that it works. Run the whole
scenario against the deployed local environment and get it green before handing
off:

```bash
./run_scenarios.sh tickets/<TICKET-ID>/<scenario>.yaml
```

The scenario is not grounded until it runs clean end to end — setup, action,
every assertion, and teardown all green. A failing first run is normal; iterate.

When a step fails, debug from real evidence, never a guess:

1. A publish that returns HTTP 200 but produces no row failed in a background
   transaction — the service container log is the only record. Find the service
   container with `docker compose ps`, then read it:
   `docker logs <container> 2>&1 | grep -iE 'error|exception'`.
2. Read the exception and its `class:line` — it names what the code could not
   find (a note field with no value, a query that returned no row).
3. Follow that `class:line` to the query or table it reads and the column or
   joined row it requires.
4. Add the missing row or column to setup. Fix the setup, not the product code.
5. Re-run. Repeat until green. Stay on the one failing path the log names; do
   not trace unrelated paths.

Grounding has the power to complete the work on its own: run the scenario, read
the container log, `docker exec` into the container to inspect state, run
read-only queries against the deployed databases, and read the exact code the
exception points to; then change the scenario's setup — add the missing rows or
columns, correct the data, split a bad statement — and re-run. Iterate as many
times as the real errors require, until it runs clean. These are grounding's own
actions on the one failing path the evidence names, and they need no approval. It
does not fix product code or render the QA verdict.

Only a scenario that ran clean is handed to VALIDATE.

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
- "The schema defines the relationship" — DDL proves legal structure, not that
  the chosen content actually carries the joined row; confirm the relationship
  with a query against the deployed database.

## Red Flags

- Setup covers fewer joins than the production read.
- A reference row is proved to exist, but the scenario-owned row never assigns
  the foreign/join key that connects to it.
- Analysis stops at the changed method instead of the asserted output.
- A selected field is consumed without fallback but omitted from setup proof.
- A publish/start response is the only proof for asynchronous behavior.
- Schema SQL is written into a product repository.

## Verification

From `scenarios/`, run and read both:

```bash
python3 schema_validate.py --file <path>
./run_scenarios.sh tickets/<TICKET-ID>/<scenario>.yaml
```

Return:

- exact YAML path;
- mapping from each ticket behavior proven in the deployed environment to its
  assertion;
- the compact row table and source citations;
- schema artifact/version and selected production route;
- `--services` and `DB_DEPLOY_TYPE` unions;
- schema command output;
- the clean runner report (`report.html` / exit result) showing every step green;
- `RETURN TO SPECS` ambiguity, if any; otherwise none.

Before returning, reread the YAML rather than the planning notes and compare
its inserts and precondition join with the compact row table. If they differ,
repair the YAML, rerun schema validation, and re-run the scenario until it passes.

Do not deploy, approve the YAML, or reinterpret the ticket. Hand the grounded
scenario — proven by a clean run — to VALIDATE.
