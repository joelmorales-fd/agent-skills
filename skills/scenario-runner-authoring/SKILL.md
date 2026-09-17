---
name: scenario-runner-authoring
description: Produces the first-draft scenario for one docker-director2 ticket: determines the services and databases it needs and maps every behavior in the specification to a scenario skeleton. Use during the SCENARIOS stage. Real ids and data are resolved later, in SCENARIO GROUND. Does not deploy or run scenarios.
---

# Scenario Runner Authoring

## Overview

Produce the first draft of one ticket scenario: determine the services and
databases it needs, and map every behavior in the specification to a scenario
skeleton. Real ids and data are not resolved here — that is done in SCENARIO
GROUND, after deploy.

## When to Use

Use this in `lean-scenario-acceptance`'s SCENARIOS stage. Write the draft
scenario under `scenarios/tickets/<TICKET-ID>/`, record the services and
databases it needs, run schema validation on the draft (`schema_validate.py`
from `scenarios/`), report the result, and stop. The Lead checks the draft
before DEPLOY.

## Read before writing

Read all of these directly:

1. The accepted `specification.md`, relevant investigation/code-guide, and the
   branch's code changes.
2. `scenarios/AUTHORING.md`, `scenarios/DESIGN.md`, and `scenarios/README.md`.
3. Find one closest applicable scenario under `scenarios/` with a targeted
   search and use it for runner syntax; do not inventory every scenario.
4. The code route the change touches — enough to name the tables, services, and
   databases the scenario needs. Concrete row values are not resolved here; that
   is Step 2.

## What the draft contains

The draft is a scenario skeleton, not a runnable scenario:

1. The services and databases the scenario needs, taken from the code route.
2. Every Given/When/Then in the specification mapped to a scenario step (setup,
   action, assertion, teardown), using an existing scenario for runner syntax.
   Each required assertion appears as a step; its exact values are filled in
   during SCENARIO GROUND.
3. Placeholders where real ids and data will go. Do not invent ids or data
   here — SCENARIO GROUND resolves them against the deployed databases.

## Return

- the draft path under `scenarios/tickets/<TICKET-ID>/`;
- the services and databases the scenario needs;
- `RETURN TO SPECS` for one concrete behavior or API ambiguity, if any;
  otherwise none.

Do not deploy, run scenarios, resolve real ids, or approve the draft. Report the
draft to the Lead for the move to DEPLOY.
