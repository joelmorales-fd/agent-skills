---
name: lean-scenario-acceptance
description: Leads acceptance validation of one completed director2-aws ticket by deploying it into the shared docker-director2 lower env and running acceptance scenarios against it. Use after a lean-development-workflow ticket reaches COMPLETE, invoked manually against that ticket's directory, one ticket at a time.
---

# Lean Scenario Acceptance

Loop 2: takes a ticket loop 1 already marked COMPLETE and proves the change
actually works against a live deployed env, not just against a unit test.
`lean-` ties it to `lean-development-workflow` (loop 1); `scenario` names the
mechanism (the runner); `acceptance` names the purpose (QA in a live env).

## You can call other skills — and you must

Delegate the actual deploy mechanics to **`docker-director2-deploy`** — write
`environments.env`, bring the env up, poll health. Never hand-roll
`local-up.sh`/docker calls yourself in this skill. This mirrors loop 1's
delegation of the harness build+test to `director2-harness-test`: the lead
orchestrates, a narrow skill executes. Running the scenarios themselves
(`run_scenarios.sh`) is the QA lead's own action in VALIDATE, not something
`docker-director2-deploy` does — that skill's job ends at a healthy env.

## The organization

| Role | Job |
|---|---|
| **Lead** | Runs the stage loop, assigns each stage, decides PASS/FAIL/BLOCKED, writes `scenario-acceptance-state.md`. Never authors scenarios, never deploys, never renders the verdict itself. |
| **Engineer** | Authors the acceptance scenarios (YAML) from the ticket's frozen spec package **and the real code diff already in the repo** — never a description of either. |
| **SRE** | Invokes `docker-director2-deploy` to get the change running in the shared lower env, healthy. |
| **QA lead** | An independent employee. Reads frozen `specification.md` + the scenario YAML + the raw runner output directly, never the Engineer's or SRE's narrative. Writes `scenario-acceptance-code-review.md` — the lead's hand never touches it, same principle as loop 1's `code-review.md`. |

## The four stages

```text
SCENARIOS ──► DEPLOY ──► VALIDATE ──► DECISION
                                        │
                          PASS → validated
                          FAIL → reopen the ticket (back to loop 1) or park

any stage ──► BLOCKED   (env unavailable, VPN/images down, needed decision)
```

### SCENARIOS

**Goal:** the acceptance scenarios for the change exist, mapped to
`specification.md`'s Gherkin.

- Assign the **Engineer**. They read `specification.md` (Gherkin),
  `02-investigation.md`, `04-code-guide.md`, and the real code diff, fresh —
  to find every surface the change actually touches (a DB table, an
  API/followup, a cache/queue effect), never assumed from a description.
- They then write the scenario YAML itself per docker-director2's own
  `scenarios/AUTHORING.md` — step shapes, assertion tightness, the
  pre-commit checklist. That doc is canonical for *how* to write a scenario;
  read it top to bottom before touching any YAML, and copy the closest
  `scenarios/examples/` file rather than inventing new shapes.
- Built in one pass, skeleton and ids together, once local DBs are up (see
  DEPLOY below) — concrete ids/hierarchies come from a live
  `sql: SELECT ... capture:` query against the live local DB, never copied
  from a harness fixture's own throwaway inserts.
- **Exit:** scenarios exist, mapped to real `specification.md` behaviors.
- **Back-routing:** none — this is the first stage. A scope/behavior problem
  routes to loop 1's SPECS instead, not backward within loop 2.

### DEPLOY

**Goal:** the completed change is running in the shared lower env, healthy.

- Assign the **SRE**. They call `docker-director2-deploy`, passing the
  changed service's version key and the `DB_DEPLOY_TYPE` the scenario's
  mutation/assertion need implies:

  | Scenario asserts on… | `DB_DEPLOY_TYPE` needs |
  |---|---|
  | nothing (read-only) | `AWS` |
  | a direct DB read | `router` |
  | `contentSearch` | `router,data1,data2` |
  | publish/source-state assertion | `CIS` |

  **Union every row the scenario actually asserts on — never pick one row.** A
  scenario asserting more than one surface (e.g. a direct DB read *and*
  `contentSearch`) needs the union of both rows' DBs. Passing only one row's
  answer when the scenario needs more isn't a behavior failure, it's a DEPLOY
  that starts an env missing a DB the scenario needs — the Engineer must name
  every surface the scenario asserts on, not just its dominant one.

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
2. **Run + evaluate** — the QA lead itself runs `./run_scenarios.sh
   <TICKET-ID>` from `scenarios/` against the env DEPLOY already brought up
   healthy, always passing the ticket id explicitly (bare
   `run_scenarios.sh` only runs `scenarios/examples/*.yaml` and silently
   skips the ticket), then reads the runner's own output (`report.html`/
   JUnit) directly — never the Engineer's or SRE's claim.

The QA lead writes `scenario-acceptance-code-review.md`, fed frozen `specification.md` + the
scenario YAML + raw runner output — never a narrative summary.

- **Exit:** a verdict with evidence (PASS/FAIL + findings).
- **Back-routing:** go back to SCENARIOS for a blocking coverage finding
  (hollow assert). Go back to DEPLOY if the failure is environmental, not
  behavioral.

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
never jumps straight to a PASS/validated DECISION.

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

## Trigger

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
- The DEPLOY stage's result came from `docker-director2-deploy`'s real
  output (its Health section), not a paraphrase.
- `scenario-acceptance-code-review.md` cites specific runner evidence (report path, exit
  code, specific failing assertion) for its verdict — this is where the
  exit-code/report-path evidence lives, since the QA lead runs the scenarios
  in VALIDATE, not DEPLOY.
