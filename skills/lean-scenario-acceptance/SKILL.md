---
name: lean-scenario-acceptance
description: Leads acceptance validation of one completed director2-aws ticket by deploying it into the shared docker-director2 lower env and running acceptance scenarios against it. Use after a lean-development-workflow ticket reaches COMPLETE, invoked manually against that ticket's directory, one ticket at a time.
---

# Lean Scenario Acceptance

## Overview

Loop 2: takes a ticket loop 1 already marked COMPLETE and proves the change
actually works against a live deployed env, not just against a unit test.
`lean-` ties it to `lean-development-workflow` (loop 1); `scenario` names the
mechanism (the runner); `acceptance` names the purpose (QA in a live env).

## You can call other skills — and you must

This workflow **delegates execution to other installed skills** rather than
reimplementing them. You *can* **use** them, and you are expected to:

- **scenario authoring** → **use the `scenario-runner-authoring` skill.**
  The Engineer writes the YAML and its evidence-backed data contract. Do not
  hand-author the scenario as the Lead.
- **scenario review** → **use the `scenario-runner-validation` skill.**
  It independently accepts the exact YAML for DEPLOY or returns it for repair;
  the Engineer never approves its own work.
- **deployment** → **use the `docker-director2-deploy` skill.**
  That skill writes `environments.env`, runs `local-up.sh`, and polls health.
  Do not run `local-up.sh` or Docker commands directly from this workflow.

## The organization

| Role | Job |
|---|---|
| **Owner** (the human) | Already approved loop 1's spec. Resolves genuine business/spec questions and blockers; does not drive routine stage transitions. |
| **Lead** (you) | Manages the process: decides the next step, assigns bounded work, validates results, gathers real evidence through the delegated skills, writes `scenario-acceptance-state.md`, transitions stages, and keeps the owner informed. Never authors scenarios, deploys, or renders the QA verdict. **You are the final approver of validation:** the owner approves the Loop 1 specification once; from there, you own the completion call. Scenario Review, deployment health, runner output, and QA verdict — never is a reported pass. If you cannot stand behind the evidence, the ticket is not PASS. |
| **Engineer** (employee agent) | Uses the `scenario-runner-authoring` skill to create the acceptance YAML from the frozen ticket package and the actual code diff in the repository — never summaries of either. |
| **Scenario reviewer** (employee agent) | Independently uses the `scenario-runner-validation` skill to review the Engineer's exact YAML before DEPLOY. Returns **ACCEPTED FOR DEPLOY**, **RETURN TO SCENARIOS**, or **RETURN TO SPECS** with evidence. Never edits or repairs YAML, deploys, or runs scenarios. |
| **SRE** (employee agent) | Builds the change's image. After a successful build, uses the `docker-director2-deploy` skill to configure and deploy the required services, then confirms their health. Does not author scenarios, run them, or decide the acceptance verdict. |
| **QA lead** (employee agent) | An independent employee. Reads frozen `specification.md` + the scenario YAML + the raw runner output directly, never the Engineer's or SRE's narrative. Writes `scenario-acceptance-code-review.md` — the lead's hand never touches it, same principle as loop 1's `code-review.md`. |
| **Senior Engineer** (employee agent) | When a scenario, build, environment, or product failure needs debugging, root-causes it: reads the relevant sources, reproduces the failure, tests hypotheses, and returns the smallest evidence-backed path to continue. The Lead monitors the diagnosis and acts on it; the Lead never debugs the failure or asks the owner to classify it. |

## The five stages

```text
SCENARIOS ──► SCENARIO REVIEW ──► DEPLOY ──► VALIDATE ──► DECISION
                                                      │
                                        PASS → Lead sign-off 
                                        FAIL → Lead reviews the evidence and assigns the next action

any stage ──► BLOCKED
```

## Autonomy after approval

**Loop 2 is already approved.** You lead acceptance to validated —through
SCENARIOS, SCENARIO REVIEW, DEPLOY, VALIDATE, and DECISION—assigning work,
validating, correcting, and transitioning without asking the owner to move it
forward. Stop only for a **genuine external execution blocker**. Never ask the owner to type “continue.”

## Staying in sync

The Lead serializes state-changing work so employees do not drift out of sync:

- **One coordinator** — only the Lead decides the next step and writes
  `scenario-acceptance-state.md`.
- **One sync point** — read `scenario-acceptance-state.md` before every
  action, write it after, and brief every employee from the current state,
  never a stale copy.
- **One active state-changing assignment at a time** — do not open the next
  until the current result is back and validated. Read-only investigations may
  run in parallel only when they cannot change or rely on the same output.
- **Validate before accepting and before the next assignment** — reject a
  result built on stale inputs instead of merging it into the workflow.
- **No employee-to-employee handoffs** — all work flows employee → Lead →
  employee.

## The ticket directory

Loop 2 runs against the **same ticket directory loop 1 already used** (e.g.
`director2-aws/AVOD-458-Testing/`). It reads loop 1's frozen files there and
writes only its own new files — it never opens a file loop 1 wrote for
writing:

```text
<ticket-dir>/                     (unchanged from loop 1)
  state.md            loop 1's status/history        — loop 2 reads, never writes
  specification.md    loop 1's approved Gherkin       — loop 2 reads, never writes
  02-investigation.md, 04-code-guide.md, ...          — loop 2 reads, never writes
  code-review.md       loop 1's judge report           — loop 2 reads, never writes

  scenario-acceptance-state.md         loop 2's own status/history    — NEW, lead writes
  scenario-acceptance-code-review.md   QA lead's independent verdict  — NEW, QA lead writes
```

Both new names are deliberately distinct from loop 1's `state.md`/`code-review.md`
— same directory, so a collision would silently overwrite loop 1's file instead
of adding a new one.

In short: read `state.md`, `specification.md`, `02-investigation.md`,
`04-code-guide.md`, `code-review.md` (never write them); write
`scenario-acceptance-state.md` (mirrors `state.md` — stage, next action, append-only
History) and `scenario-acceptance-code-review.md` (mirrors `code-review.md` — the QA lead's
independent report). Templates for both:
`assets/templates/scenario-acceptance-state.md` and
`assets/templates/scenario-acceptance-code-review.md`.

## The control loop

Same shape as loop 1's control loop, run inside whichever stage is active:

```text
1. READ    scenario-acceptance-state.md — what stage, and the one unmet exit criterion?
2. DECIDE  the single smallest next action.
3. DO      assign the bounded task to the Engineer/SRE/QA lead for this stage.
4. JUDGE   the real result yourself — read the changed YAML/diff and raw
           command output/report, never the employee's summary — then advance,
           stay, go back, or block.
5. WRITE   the outcome + next action into scenario-acceptance-state.md, append
           one History line naming what was actually verified — never advance
           past JUDGE on a summary alone.
6. LOOP    back to 1 — in the same turn.
```

**The Lead knows everything because it reads everything.** When any employee
returns a result, do **not** accept its summary. If the employee changed a
file, read the exact diff first. Then read the role's primary evidence:

- **Engineer** — the exact YAML, its diff, and schema-validation output.
- **Scenario reviewer** — the exact YAML, schema-validation output, and
  independent review evidence.
- **SRE** — `build.log` and the deployment skill's health output.
- **QA lead** — the runner's JUnit XML, `report.html`, and the independent QA
  verdict artifact.
- **Senior Engineer** — the reproduction and complete diagnosis evidence
  chain.

The employee's summary and PASS/FAIL/BLOCKED label are *claims*; the diff,
raw output, and artifacts are the *evidence*. Record what the evidence
actually showed in the History line, not "GREEN" or an employee conclusion.
The Lead decides the state from that evidence and the current stage's exit
criterion. A report the Lead did not inspect is not evidence.

## Stages in detail

### SCENARIOS

**Follow `scenario-runner-authoring`** — it is the process to run for reading
the frozen ticket package and real code diff, establishing the data contract,
writing the YAML, and validating its schema. It is a **process, not text to
reproduce.**

- Assign the **Engineer** to invoke `scenario-runner-authoring`. Before
  writing YAML, the Engineer reads `specification.md` (Gherkin),
  `02-investigation.md`, `04-code-guide.md`, and the real code diff. Those
  sources identify every database table, API/followup, cache, or queue the
  change touches; never assume that information from a description.
- The Engineer then writes the scenario YAML itself according to
  docker-director2's `scenarios/AUTHORING.md`, `scenarios/DESIGN.md`, and
  `scenarios/README.md`. The Engineer reads all three before touching YAML.
  These documents are canonical for the available step shapes, local-data
  patterns, and runner behavior. The Engineer searches for the closest
  applicable scenario anywhere under `scenarios/`, including ticket scenarios;
  do not limit the search to `scenarios/examples/`.
- The Engineer writes the scenario YAML before DEPLOY from the ticket and the
  sources above. Use only data setup, discovery, and cleanup behavior
  established by the ticket, source code, schemas, fixtures, existing
  scenarios, or harness test files changed by the ticket. Do not invent fixture
  IDs, data, or cleanup policy. A harness test file can help establish a
  hierarchy or relationship: the Engineer translates the rows required by the
  selected feature query using the current schemas and one valid row example.
  Creating those rows is SCENARIOS work, not a reason to request a live fixture
  contract or deployed fixture from the user.
- For all data the test needs, show where it comes from:
  - If the source shows it is already in the deployed database, add a YAML
    check that all needed rows and values exist before running the feature.
  - Otherwise, add YAML setup based on the code or schema, then immediately
    check that all needed rows and values were created.
  Review the setup before DEPLOY. Run it only in the deployed databases.
- **Done:** the Engineer has written scenarios for every Given/When/Then in
  `specification.md`.
- **When to return to SCENARIOS:** - If the scenario does not have the data it needs, 
  the Lead sends  it back to SCENARIOS. The Engineer works out the required data 
  before the scenario movesforward.
  
  Not finding the same current value in the ticket test data does not block the
  work. A hierarchy found only in a harness test does not block the work if the
  current schema and production code show how to create it in the local
  database. If the required behavior is unclear or needs to change, the Lead
  sends the ticket to read Loop 1 SPECS.
  
  At the end of the scenario, teardown removes the rows the scenario created or
  inserted. The cleanup SQL must delete only that scenario’s data.
  
### SCENARIO REVIEW

**Follow `scenario-runner-validation`** — it is the process to review the
scenario YAML before DEPLOY. It checks that the YAML uses real sources, handles
test data safely, and requires the right services and databases. It is a
**process, not text to reproduce.**

- Assign the **Scenario reviewer** to invoke `scenario-runner-validation`.
  The reviewer reads the actual YAML and sources, performs its schema check,
  and returns its stated verdict with evidence.
- The Lead reads the branch’s code diff, the YAML, the review evidence, and the
  schema check output. Confirm that the reviewer checked the current YAML
  against the code changes before accepting the verdict. Record the accepted
  YAML path, test-data plan, and required services and databases in
  `scenario-acceptance-state.md`.
- Start DEPLOY only after the reviewer returns **ACCEPTED FOR DEPLOY**.
- On **RETURN TO SCENARIOS**, the Lead reads the exact missing evidence and
  assigns the Engineer to repair the YAML. With the database running, the
  Engineer can query it for the data needed for the repair, if the Lead assigns the task.

### DEPLOY

During DEPLOY, the SRE builds the change and deploys it to the shared lower
environment using `docker-director2-deploy`. The SRE gives the Lead the
deployment result and health checks.

- Assign the **SRE**. Before they can build the change's image, they must
  first resolve `director2-aws-build` — the container the build runs
  inside — in this order. Check state with this exact command — no `-it`,
  no TTY needed, no other check invented:

  ```
  docker inspect --format="{{ .State.Running }}" director2-aws-build
  ```

  - `true` → running and valid → reuse it.
  - Errors (container not found) → absent → create it with the `buildenv`
    alias below. Keep that shell session open and run the build steps
    (below) inside it directly — an absent-case container is interactive
    and auto-removed the instant its shell exits (a dropped connection, a
    timeout, or a tool call ending destroys it and any build state in it),
    so do not exit the shell and try to `docker exec` into it from a
    separate step:

    Run it in a PTY-capable terminal session; the terminal invocation must
    allocate a TTY. `bash -ilc` alone does not allocate one.

    ```
    bash -ilc 'cd $HOME/src/director2-aws && buildenv'
    ```

    `server-build` image must already exist locally — this workflow never
    builds, pulls, publishes, or replaces it, and never rebuilds
    `server-build` to "fix" a build failure.
  - `false`, or running but not the configured image/mount → exists but
    stopped or invalid → stop with the exact blocker. Do not remove or
    replace the container, or invent another container path.

  **VERIFY:** quote this command's actual output in
  `scenario-acceptance-state.md` before acting on it. A permissions error,
  a TTY error, or any other error from a *different* command you tried
  instead is not evidence about the container's state — rerun the exact
  command above and report what it, specifically, printed.
  - Once it's running, run this exact command inside it, capturing its
    output to a file so the raw text survives past this step:

    ```
    docker exec director2-aws-build bash -c \
      'cd /director2-aws/director2 && ./gradlew buildDockerImageLocally' \
      > build.log 2>&1
    ```

    This builds the changed service's image from the current code — the
    real build, not a rebuild-from-cache — and tags it `:latest` in the
    local Docker store, the exact image `docker-director2-deploy`'s CONFIG
    step picks up via `--director-version local`.

  - **Transient infra / interruption** (VPN drop, Nexus/Ryuk flake, buildenv
    container death, client disconnect, timeout) — **retry freely; it does not
    burn the 5-cap.** It is not a "stable problem"; nothing was learned and
    nothing was tried. If the same infra failure keeps recurring, that's a
    diagnosis worth reporting (why the environment won't hold), not a spent
    attempt budget.
  - **JUDGE before writing BLOCKED (control-loop step 4):** open `build.log`
    yourself and quote its actual tail in `scenario-acceptance-state.md`. A
    description of the error ("the build failed because of X") is not
    evidence and does not satisfy this step — only the file's own text does.
    If you have not read `build.log`, you have not verified the failure.
- Only once that image is built does the SRE call `docker-director2-deploy`.
  The accepted Scenario Review supplies both `--services` and
  `DB_DEPLOY_TYPE`; the SRE uses those values and does not guess from the YAML.

  **Confirmed operations**

  | Scenario operation | `--services` must include | `DB_DEPLOY_TYPE` must include |
  |---|---|---|
  | `disMediaCorePublishStream*` | `CIS` | `CIS` |
  | `contentSearch` | `router,data1,data2` | `router,data1,data2` |
  | `sql` with `db: router` | `router` | `router` |
  | `sql` with `db: cis` | `CIS` | `CIS` |

  For an operation not listed above, the Engineer analyzes it before the
  scenario is accepted. Do not infer its requirements from its name, endpoint,
  or a broad category.

  | Scenario operation | Code route checked | Services required | Local DBs required |
  |---|---|---|---|
  | each `api` step | Trace the request through router/configuration to its target and the downstream path needed by its assertion | Record every required runtime service | Record every DB required by that path/state |
  | each `sql` step | Read the declared `db:` target and its owning service | Record the owning service when it must run | Record the named database |
  | each `wait` step | Analyze its nested `api` or `sql` operation the same way | Add its services to the union | Add its DBs to the union |

  Union every applicable confirmed and analyzed row in both columns. If the
  route cannot be proven from code or configuration, return to SCENARIOS for
  investigation; do not deploy an assumed environment.

  Before calling `docker-director2-deploy`, the lead compares that union with
  the actual `--services` and `DB_DEPLOY_TYPE` values. Any `contentSearch`
  requires `router,data1,data2` in both values; otherwise return to SCENARIOS
  and do not run QA.

- Shared, long-lived env in a batch (up once, deploy successive changes) —
  not per-ticket teardown. Two changes to the same base image basename
  (e.g. two router/main tickets) queue and run one at a time; different
  basenames run concurrently against the same shared env.
- **Exit:** env up, change deployed, health confirmed (the deploy skill's
  own HEALTH step).
- **Back-routing:** go back to SCENARIOS only if the deploy reveals the
  scenario assumed the wrong DB set. **BLOCKED** for a genuinely unavailable
  capability (VPN down, image build failure) — not a reason to improvise
  around the deploy skill.

### VALIDATE

The QA lead runs the approved scenario YAML against the deployed environment, 
reads the runner’s result files, and decides whether the scenario proves the 
deployed change works.

1. **Coverage check (mechanical)** - The QA lead compares every Given/When/Then 
  in `specification.md` with the scenario YAML. Each required result must have a YAML 
  check that reads theresult produced by the deployed change.

  - Check response text with an anchored `body_regex`, not a loose
    `body_contains` that could match unrelated text.
  - Check the required database values with exact `row.N.column` checks, not
    only `rows: N`.
  - For work that finishes later, use `wait:` to check the real result; do not
    use `sleep` instead of a check.
  - For an expected absence, check zero rows (`rows: 0` or `row.0.cnt: 0`).
    “No error” does not prove that the result is absent.

  A scenario is not accepted when its checks could pass with the wrong result.
  Go back to **SCENARIOS** if the checks fail or are insufficient.

2. **Run + evaluate** - The QA lead runs the accepted scenario YAML from `scenarios/`
  against the healthy deployed environment:

  `./run_scenarios.sh tickets/<TICKET-ID>/<scenario>.yaml`

  Running `./run_scenarios.sh` without the YAML path runs only
  `scenarios/examples/*.yaml`; it does not run ticket scenarios.

  The scenario YAML creates and checks its own data in the deployed databases.
  The QA lead reads the runner’s `report.html` and JUnit XML directly. The QA
  lead does not add data by hand or change the YAML.


The QA lead writes `scenario-acceptance-code-review.md` using the frozen
`specification.md`, the scenario YAML that ran, and the runner’s raw output.
The report records the QA lead’s findings from those files, not a summary of
another person’s claim.

The QA lead returns `scenario-acceptance-code-review.md` and the raw runner
output to the Lead. The report says whether the scenario completed its setup,
reached its final product check, and passed or failed. It records any problem
found in the YAML, the deployed environment, or the product result.


- The QA lead sends the result to the Lead: PASS or FAIL, with findings and
  evidence.


### DECISION

**This is the Lead’s acceptance decision — not an automatic transition.**
Scenario Review acceptance, a healthy deployment, and the runner result are the
inputs. The Lead reads the exact YAML, review evidence, deployment health, and
runner report before deciding PASS or FAIL. A PASS means the deployed change
produced every required result. A FAIL means the accepted scenario reached its
final check and the deployed change produced a wrong result. If any evidence is
only a claim, the Lead verifies it before making the decision.


### BLOCKED

Only after you've tried the safe options available. Record the origin
stage and the one exact human action needed to resume. Never jumps straight to
PASS.

## Delegation is the model

You always delegate acceptance work via a short assignment: the exact inputs
the employee may read, the single deliverable, the files it may write
(everything else off-limits), what “done/pass” looks like, and whether it may run an
approved command. The employee returns a result with real evidence; you
validate it against the current state, then accept or reject. Your only
hands-on action is running an approved command to gather real evidence — that
is verifying the work, not doing it.

## When to Use

Invoked manually, as a skill, against one COMPLETE ticket's directory — one
ticket at a time. Not auto-chained onto loop 1's COMPLETE, not batched. Wire
an automatic trigger later, once this is validated standalone.

## Non-negotiables

- Read `scenario-acceptance-state.md` before acting; write it after every
  action.
- Delegate acceptance work; never author scenarios, deploy, run scenarios, or
  write the QA report yourself.
- Evidence is a real scenario run against a real deployed environment — never
  a claim about one.
- Accept the artifact, not the summary. Read what each employee returned and
  record what it showed in the History line.
- `scenario-acceptance-state.md` and
  `scenario-acceptance-code-review.md` are additive only. Never edit a file
  Loop 1 wrote.
- One active state-changing assignment at a time.
- A stalled employee is a failed delegation. Reissue the same bounded
  assignment to a fresh employee; never do its work yourself.
- When debugging is needed, assign the Senior Engineer. Do not debug the
  failure yourself.
- Use `docker-director2-deploy` for deployment. Do not run `local-up.sh` or
  Docker commands yourself.
- Never put a secret in a ticket file, prompt, or command argument.
- Copying an employee verdict without reading the artifact — yes. Non-negotiable 
  evidence rule.
- The QA lead writes the QA report from the raw runner output. The Lead reads
  the same output before accepting the result.

## Verification

- `scenario-acceptance-state.md` must exist in the ticket directory. Its History
  and must be append-only and include one line after every action.
- Before DEPLOY begins, the accepted scenario and the
  `scenario-runner-validation` result are recorded in
  `scenario-acceptance-state.md`.
- The DEPLOY record must include the health-check output from
  `docker-director2-deploy`.
- `scenario-acceptance-code-review.md` must say which scenario the QA lead ran.
  It must include the runner report path and the exit result.

