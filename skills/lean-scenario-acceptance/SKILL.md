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

In SCENARIOS, the Engineer must invoke **`scenario-runner-authoring`** to write
the YAML and its evidence-backed data contract. Then call
**`scenario-runner-validation`** before DEPLOY. It independently accepts or
returns the scenario; the Engineer never approves its own work. Delegate actual deploy mechanics to
**`docker-director2-deploy`** — write `environments.env`, bring the env up,
poll health. Never hand-roll `local-up.sh`/docker calls yourself in this
skill. Running scenarios (`run_scenarios.sh`) remains the QA lead's action in
VALIDATE, not `docker-director2-deploy`'s job.

## The organization

| Role | Job |
|---|---|
| **Lead** (this skill, running as an agent) | Runs the stage loop, assigns each stage, decides PASS/FAIL/BLOCKED, writes `scenario-acceptance-state.md`. Never authors scenarios, never deploys, never renders the verdict itself. |
| **Engineer** (employee agent) | Invokes `scenario-runner-authoring` to author the acceptance YAML from the ticket's frozen spec package **and the real code diff already in the repo** — never a description of either. |
| **Scenario reviewer** (employee agent) | Independently invokes `scenario-runner-validation` on the Engineer's YAML before DEPLOY. It accepts, returns to SCENARIOS, or returns to SPECS; it never edits or repairs YAML. |
| **SRE** (employee agent) | Builds the change's image, then invokes `docker-director2-deploy` to get it running in the shared lower env, healthy. See DEPLOY below for the exact build steps. |
| **QA lead** (employee agent) | An independent employee. Reads frozen `specification.md` + the scenario YAML + the raw runner output directly, never the Engineer's or SRE's narrative. Writes `scenario-acceptance-code-review.md` — the lead's hand never touches it, same principle as loop 1's `code-review.md`. |

## The five stages

```text
SCENARIOS ──► SCENARIO REVIEW ──► DEPLOY ──► VALIDATE ──► DECISION
                                                      │
                                        PASS → validated
                                        FAIL → reopen the ticket (back to loop 1) or park

any stage ──► BLOCKED   (env unavailable, VPN/images down, needed decision)
```

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
4. VERIFY  the real result yourself — the raw command output/report, never
           the employee's summary of it. A description of what failed and why
           is a claim; the actual captured stdout/stderr/report is the
           evidence, and only that satisfies this step.
5. WRITE   the outcome + next action into scenario-acceptance-state.md, append
           one History line naming what was actually verified — never advance
           past VERIFY on a summary alone.
6. LOOP    back to 1 — in the same turn.
```

**The lead knows everything, because it reads everything.** When the SRE, Engineer,
or QA lead returns a result, you do **not** accept its summary — you open the actual
file yourself: `build.log` for a DEPLOY build (see below), the output of `python3
schema_validate.py --file <path>` run from `scenarios/` for a SCENARIOS schema claim
(where `<path>` is the accepted YAML path), or the runner's `report.html`/JUnit XML for
a VALIDATE result. The summary is the employee's
*claim*; that file's content is the *evidence*, and you accept only that. Record what
the evidence actually showed in the History line, not "failed"/"passed" alone. You
cannot control or monitor what you never looked at yourself; a report you didn't open
is not evidence.

## Stages in detail

### SCENARIOS

**Goal:** the acceptance scenarios for the change exist, mapped to
`specification.md`'s Gherkin.

- Assign the **Engineer** to invoke `scenario-runner-authoring`. They read
  `specification.md` (Gherkin),
  `02-investigation.md`, `04-code-guide.md`, and the real code diff, fresh —
  to find every surface the change actually touches (a DB table, an
  API/followup, a cache/queue effect), never assumed from a description.
- They then write the scenario YAML itself per docker-director2's own
  `scenarios/AUTHORING.md`, `scenarios/DESIGN.md`, and `scenarios/README.md`.
  Read all three before touching YAML. They are canonical for the available
  step shapes, local-data patterns, and runner behavior. Search for the
  closest applicable scenario anywhere under `scenarios/`, including ticket
  scenarios; do not limit the search to `scenarios/examples/`.
- Build the scenario YAML before DEPLOY from the ticket and those sources.
  Use only data setup, discovery, and cleanup behavior established by them or
  by the ticket's real fixture/source. Do not invent fixture IDs, data, or
  cleanup policy. If the needed information is not established, return the
  evidence gap instead of fabricating a scenario.
- Source-backed does not mean every literal must appear unchanged in one
  source. A plan may combine compatible evidence: one source can establish
  the required domain relationships while an existing scenario establishes
  how local test values, active time windows, ownership, and restoration are
  handled. Record each source and derivation. A value with no such derivation
  is still invented.
- For every required data condition, use one evidenced path:
  - If source evidence proves DEPLOY supplies it, add a YAML precondition
    assertion that verifies the complete required state before the feature
    action.
  - Otherwise, add source-backed setup and an immediate precondition assertion
    that proves the complete required state was created. The setup is reviewed
    before DEPLOY but runs only against the deployed databases.
- **Exit:** scenario YAML exists, mapped to real `specification.md` behaviors,
  and is ready for independent review.
- **Back-routing:** a missing source or prerequisite returns to SCENARIOS for
  investigation. Before escalating to a human, record the sources searched,
  a concrete source-backed candidate plan, or why each candidate was rejected.
  Missing an exact current literal in the ticket fixture alone is not a
  blocker. A scope/behavior problem routes to loop 1's SPECS instead.

### SCENARIO REVIEW

**Goal:** independently decide whether the authored YAML is grounded and safe
enough to deploy.

- Assign the **Scenario reviewer** to invoke `scenario-runner-validation`.
  The reviewer reads the actual YAML and sources, performs its schema check,
  and returns its stated verdict with evidence.
- The lead reads that evidence itself, including the schema command output.
  Record the accepted YAML path, data plan, and deployment union in
  `scenario-acceptance-state.md`.
- **Exit:** only **ACCEPTED FOR DEPLOY** enters DEPLOY.
- **Back-routing:** **RETURN TO SCENARIOS** returns the precise evidence gap to
  the Engineer; **RETURN TO SPECS** returns the behavior ambiguity to loop 1.
  Neither result authorizes an invented repair or deployment.

### DEPLOY

**Goal:** the completed change is running in the shared lower env, healthy.

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
  - **VERIFY before writing BLOCKED (control-loop step 4):** open `build.log`
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

**Goal:** the QA lead confirms the deployed change actually satisfies the
scenarios, and that the scenarios themselves prove real behavior (not
hollow).

Two checks — mirrors why loop 1 has both JUDGE (coverage) and MUTATION
(real-evidence), not just GREEN:

1. **Coverage check (mechanical)** — every `specification.md`
   Given/When/Then maps to a real, tight assertion in the Engineer's
   scenario YAML:
   - `body_regex` with a clear anchor, not a loose `body_contains` that
     would also match an unrelated body containing the same substring.
   - exact `row.N.col` value checks for the asserted data, not just
     `rows: N` (a row-count-only check passes even with the wrong value).
   - a real `wait:` poll on actual state for anything async, not `sleep`
     standing in for an assertion.
   - a negative/absence scenario proves absence with an assert-zero
     (`rows: 0` / `row.0.cnt: 0`), not "no error was thrown."
   A scenario that runs but whose asserts are loose or hollow is a
   **blocking** finding — the acceptance-test analog of a hollow unit test.
2. **Run + evaluate** — the QA lead reads the accepted scenario YAML path,
   then runs `./run_scenarios.sh <path>` from `scenarios/` against the
   healthy env (for example, `./run_scenarios.sh
   tickets/<TICKET-ID>/<scenario>.yaml`). A bare `run_scenarios.sh` runs
   `scenarios/examples/*.yaml` and silently skips ticket scenarios. The QA
   lead lets the accepted setup run against the deployed databases, then reads
   the runner's own output (`report.html`/JUnit) directly — never the
   Engineer's or SRE's claim. Do not manually seed data or rewrite YAML here.

The QA lead writes `scenario-acceptance-code-review.md`, fed frozen `specification.md` + the
scenario YAML + raw runner output — never a narrative summary.

- **Exit:** a verdict with evidence (PASS/FAIL + findings).
- **Back-routing:** go back to SCENARIOS for a blocking coverage finding
  (hollow assert), a failed data precondition, or a service-side processing
  failure caused by missing scenario-created dependencies. For asynchronous
  APIs, an accepted/start response is not completion; inspect the failed
  downstream wait/assertion and relevant service error before classifying the
  result. Return incomplete fixture construction to SCENARIOS rather than
  treating it as a product failure. Go back to DEPLOY if the failure is
  environmental, not behavioral.

### DECISION

**Goal:** route the verdict.

- **PASS** → the change is validated; loop 2 is done for this ticket/batch
  entry.
- **FAIL** → fail-routing (which loop-1 stage to reopen — TDD for a code
  bug, SPECS for wrong behavior) is **still an open question**. Until it's
  resolved, park the ticket for human triage rather than guessing which
  loop-1 stage to reopen. Fail-fast/park philosophy holds, same as loop 1.

### BLOCKED

Any stage enters BLOCKED when a required env, VPN, image, or decision is
genuinely unavailable — and only after trying the safe options available.
`scenario-acceptance-state.md` records the stage it came from and the one exact thing a
human must provide to resume. Infra deps (VPN, `docker.mgo.com` images,
downloaded DBs) are transient on flake, not an automatic block. BLOCKED
never jumps straight to a PASS/validated DECISION. SCENARIOS is not BLOCKED
merely because the ticket fixture lacks a current literal value; complete the
required repository search and candidate analysis first.

## When to Use

Invoked manually, as a skill, against one COMPLETE ticket's directory — one
ticket at a time. Not auto-chained onto loop 1's COMPLETE, not batched. Wire
an automatic trigger later, once this is validated standalone.

## Non-negotiables

- Evidence is a real scenario run against a real deployed env — never a
  claim about one.
- One active assignment at a time; the lead is the only coordinator.
- The lead never authors scenarios, never deploys, never renders the
  verdict — each is a distinct role, same separation-of-duties reason loop 1
  keeps the Judge independent from the Senior Engineer.
- DEPLOY cannot begin without `scenario-runner-validation` accepting the
  exact YAML path and its deployment union.
- `scenario-acceptance-state.md` and `scenario-acceptance-code-review.md` are additive only. Never edit a
  file loop 1 wrote.
- Fail routing is unresolved — on FAIL, park for human triage. Don't invent
  a routing rule to avoid stopping.

## Common Rationalizations

- "The QA lead can just trust the Engineer's scenario ran fine" — red flag;
  mirrors loop 1's "accept the diff, not the summary." The QA lead reads the
  raw runner output itself.
- "Skip DEPLOY's health check, the env was fine an hour ago" — the deploy
  skill always re-polls; a shared env drifts between tickets.
- "The scenario's row-count assertion is good enough" — no; a hollow
  assertion is a blocking VALIDATE finding, not a nitpick.
- "The ticket fixture's dates are historical, so a live scenario needs
  invented data" — not established until applicable ticket scenarios and
  their source-backed time/setup patterns have also been investigated.
- "FAIL clearly means a TDD bug, just reopen loop 1's TDD stage" — fail
  routing isn't resolved yet; park it instead of guessing.

## Red Flags

- The lead calls `local-up.sh`/docker directly instead of delegating to
  `docker-director2-deploy`.
- The SRE (or anyone but the QA lead) runs the scenarios or reads the
  runner's report — that's the QA lead's own action in VALIDATE.
- `scenario-acceptance-code-review.md` is written by anyone other than the QA lead, or is
  based on a narrative instead of raw runner output.
- A file loop 1 wrote (`state.md`, `specification.md`, `code-review.md`,
  etc.) gets edited.
- A FAIL result gets auto-routed to a specific loop-1 stage without human
  triage.

## Verification

- `scenario-acceptance-state.md` exists in the ticket directory and its History is
  append-only, one line per stage transition, matching loop 1's `state.md`
  convention.
- Every `specification.md` Given/When/Then has a corresponding tight
  assertion in the scenario YAML (no hollow `rows: N`/`body_contains`-only
  checks).
- The accepted scenario path, its `scenario-runner-validation` verdict, and
  deployment union are recorded before DEPLOY starts.
- The DEPLOY stage's result came from `docker-director2-deploy`'s real
  output (its Health section), not a paraphrase.
- `scenario-acceptance-code-review.md` cites specific runner evidence (report path, exit
  code, specific failing assertion) for its verdict — this is where the
  exit-code/report-path evidence lives, since the QA lead runs the scenarios
  in VALIDATE, not DEPLOY.
