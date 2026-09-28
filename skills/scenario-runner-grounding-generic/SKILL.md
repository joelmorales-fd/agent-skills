---
name: scenario-runner-grounding-generic
description: Grounds one drafted ticket scenario against the deployed data stores of a repository other than director2-aws — resolves the real ids and data, finalizes the setup, precondition, checks, and teardown, then runs the scenario against the deployed service until it passes. Use during the SCENARIO GROUND stage, after DEPLOY, when the repository is not director2-aws. Does not deploy or render the QA verdict.
---

# Scenario Runner Grounding (Generic)

## Overview

Ground one drafted ticket scenario against the deployed environment of a
repository other than director2-aws. Resolve the real ids and data the draft
left as placeholders, finalize the setup, the precondition, the checks, and the
teardown, then run the scenario against the deployed service until it passes.

For director2-aws, use `scenario-runner-grounding` instead.

## When to Use

Use this in the SCENARIO GROUND stage, after DEPLOY has brought the lower
environment up. Read the draft, resolve its placeholders against the deployed
databases, write the finished YAML, run schema validation, run the scenario
until it passes, report, and stop.

The scenario runner lives in the docker-director2 repository at
`$HOME/src/docker-director2/scenarios`. Every `scenarios/` path in this skill is
relative to that repository. Write the finished YAML at
`$HOME/src/docker-director2/scenarios/tickets/<TICKET-ID>/<scenario>.yaml`


## Read the repository first

The repository's root `AGENTS.md` is the source for everything this skill cannot
know about the repository. Read it before touching the draft and take from it:

1. the data stores the deployment brings up (for example a database, a cache, or
   a queue) and how to connect to each one;
2. where the schema is, for example an init script or migrations;
3. how to call the deployed service;
4. how to read the service's logs.

Do not invent any of these. If the `AGENTS.md` does not give something the
scenario needs, report that exact gap to the Lead.

## Build the data contract first

Work as an engineer, not as an exhaustive proof search:

Before authoring the YAML, read `scenarios/AUTHORING.md`, `scenarios/DESIGN.md`, and `scenarios/README.md`. The creation file always will be a YAML and must conform to the schema defined in those documents.

1. Map each behavior that must be proven in the deployed environment to its
   real action and check. Do not repeat a behavior that Loop 1 already proved
   with unit tests.
2. Read the code path the action takes, from the request to the value the check
   reads. List only the tables, keys, joins, filters, and returned fields that can reject
   the test data or decide the checked value.
3. If the path reads no data store, say so. The scenario then needs no setup,
   precondition, or teardown, and grounding is only the clean run.
4. For each table the path reads, read its schema and query the deployed data
   store for rows that already qualify. Querying the deployed data store is how
   you find valid data; it is required, not optional.
5. Reuse the rows that already qualify, or the closest ones; they already carry
   every joined row. Insert or update only what they still lack. Do not insert
   the expected result.
6. Write the candidate YAML immediately, run schema validation, and repair only
   the concrete table, field, join, or YAML error that fails.

This skill has no `BLOCKED` outcome. It returns either a scenario that ran clean
end to end against the deployed system, or `RETURN TO SPECS` for one concrete
behavior/API ambiguity.

## Author the YAML

Before authoring the YAML, read `scenarios/AUTHORING.md`, `scenarios/DESIGN.md`, and `scenarios/README.md`. The creation file always will be a YAML and must conform to the schema defined in those documents.

Order stateful scenarios as follows:

1. Capture original state before modifying existing records.
2. Reuse the ids the data contract chose, and insert or update only
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

The scenario is not grounded until it runs clean end to end: setup, action,
every check, and teardown.

When a step fails, debug from real evidence:

1. Read the service log the way the `AGENTS.md` describes.
2. Read the exception and the `class:line` it names.
3. Follow that line to the query or field it needs.
4. Fix the scenario's setup, not the product code.
5. Run it again. Stay on the one failing path the log names.

This skill has no `BLOCKED` outcome. It returns either a scenario that ran clean
end to end against the deployed service, or `RETURN TO SPECS` for one concrete
behavior or API ambiguity.

## Common Rationalizations

- "The insert succeeded, so the test data is complete." The code path's query
  and the precondition must also accept the rows.
- "The schema defines the relationship." The schema proves a legal shape, not
  that the chosen row carries the related row; confirm it with a query.
- "The action returned success." A response that only starts work does not
  prove the work finished.

## Red Flags

- An id or value appears in the scenario that was not found in, or created in,
  the deployed data store.
- Setup covers fewer joins than the code path reads.
- The analysis stops at the changed method instead of the checked value.
- A teardown deletes rows without proof the scenario created them.
- A connection detail, schema location, or command was not taken from the
  `AGENTS.md`.

## Verification

From `scenarios/`, run and read both:

```bash
python3 schema_validate.py --file <path>
./run_scenarios.sh tickets/<TICKET-ID>/<scenario>.yaml
```

Return:

- the exact YAML path;
- the mapping from each behavior proven in the deployed environment to its
  check;
- the tables, rows, and schema source used, or a statement that the path reads
  no data store;
- the schema command output;
- the clean runner report (`report.html` / exit result) showing every step green;
- `RETURN TO SPECS` with the ambiguity, if any; otherwise none.

Before returning, reread the YAML rather than the planning notes and compare
its inserts and precondition join with the compact row table. If they differ,
repair the YAML, rerun schema validation, and re-run the scenario until it passes.

Do not deploy, approve the YAML, or reinterpret the ticket. Hand the grounded
scenario — proven by a clean run — to VALIDATE.
