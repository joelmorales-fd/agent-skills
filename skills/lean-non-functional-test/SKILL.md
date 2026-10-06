---
name: lean-non-functional-test
description: Leads non-functional testing of one ticket that lean-development-workflow (Loop 1) has completed. It deploys the change, has the QA lead write a Test Plan from the changed code, has an independent Judge do a code review of that Test Plan, has the QA lead run it, and ends with the Lead's PASS or FAIL. It covers performance anti-pattern detection, and maintainability and readability. Use after Loop 1 reaches COMPLETE, before or after lean-scenario-acceptance (Loop 2), invoked manually against that ticket's directory, one ticket at a time.
---

# Lean Non-functional Test

## Overview

Loop 1 proves that a change behaves as its specification says. Loop 2 proves that
the same behavior holds once the change is deployed. Neither one checks how well the
change is built and how it behaves when it runs. This skill does, for one ticket that
Loop 1 has completed. It does not depend on Loop 2, so it may run before or after it.

**The one principle: a change is judged against a Test Plan that passed its code
review before anything runs.** After the change is deployed, the QA lead writes the
Test Plan. An independent Judge does a code review of it, and only an approved Test
Plan is run. A result is raw output or an approved finding, never an agent's
description of it. A Test Plan changed after its results were seen is not valid.

The skill never changes the product code, the service's image, its startup settings,
or any file that Loop 1 or Loop 2 wrote.

## What this skill tests

This skill covers two non-functional requirements, both found by reading the code:
**performance anti-pattern detection**, code whose work grows badly as its input grows,
and **maintainability and readability**, code the next person will find hard to read or
change. Nothing has to run against the service to find them.

## You can call other skills — and you must

This workflow **delegates execution to other installed skills** rather than
reimplementing them. You *can* **use** them, and you are expected to:

- **services and databases** → **use the `scenario-runner-authoring` skill.**
  In DEPLOY, the Engineer determines the services and databases the test NFR requires. 
  Do not hand-pick them as the Lead.
- **deployment** → for director2-aws, **use the `docker-director2-deploy` skill.**
  That skill writes `environments.env`, runs `local-up.sh`, and polls health.
  Do not run `local-up.sh` or Docker commands directly from this workflow.
  For any other repo, deploy with the instructions in that repo's root `AGENTS.md`
  (see DEPLOY).
## The organization

| Role | Job |
|---|---|
| **Owner** (the human) | Starts the run for one completed ticket and resolves a recorded blocker. Does not move the run between stages, and is never asked to "continue". |
| **Lead** (you) | Reads the state file, decides the next step, assigns work, reads every file an employee writes, writes `non-functional-test/state.md`, moves between stages, and makes the final PASS or FAIL decision. Never deploys, writes or reviews the Test Plan, or runs it. |
| **SRE** (employee agent) | In DEPLOY, builds the change's image. After a successful build, if the repository is director2-aws, uses the `docker-director2-deploy` skill to deploy the services that run the changed code, then confirms their health. If the repository is not director2-aws, reads the repository's root `AGENTS.md` to build, deploy, and check health. Never writes, reviews, or runs the Test Plan, and never decides. |
| **Engineer** (employee agent) | In DEPLOY, works out the services and databases the change needs, before the deploy. Never deploys, writes or reviews the Test Plan, decides, or moves the run between stages. |
| **QA lead** (independent employee agent) | In TEST PLAN, writes `test-plan.md` from the change and the deployed system, and fixes it when the code review sends it back. In RUN, runs the approved Test Plan and writes `verdict.md`. Never deploys, does the code review of its own Test Plan, fixes code, or decides. |
| **Judge** (independent employee agent) | In CODE REVIEW, does the code review of the Test Plan with a fresh context that never saw the QA lead's reasoning, and writes `code-review.md`. Never writes or runs the Test Plan, and never decides. |
| **Senior Engineer** (employee agent) | Works out why a deployment or a run failed, and returns the smallest path to continue. Never deploys, writes the Test Plan, decides, or moves the run between stages. |

## The five stages

```text
DEPLOY ──► TEST PLAN ──► CODE REVIEW ──► RUN ──► DECISION
               ▲              │
               └──────────────┘  (the Test Plan is wrong: back to TEST PLAN)

any stage ──► BLOCKED
```

| From | To | On |
|---|---|---|
| DEPLOY | TEST PLAN | the change is deployed and healthy |
| TEST PLAN | CODE REVIEW | the QA lead has written `test-plan.md` |
| CODE REVIEW | TEST PLAN | `code-review.md` finds a problem in the Test Plan |
| CODE REVIEW | RUN | `code-review.md` approves the Test Plan |
| RUN | DECISION | the QA lead has written `verdict.md` |
| any | BLOCKED | a needed capability is unavailable, or 5 attempts on the same unchanging problem |

DEPLOY comes first. QA tests the change that the SRE already deployed. The Test Plan
can depend on the deployed system, and the deployment never depends on the Test Plan,
because the skill never changes the service.

DECISION is final. BLOCKED records the stage it came from and the one exact action a
human must take, and it never jumps to DECISION.

## Autonomy after the owner starts the run

The owner starts the run **once**. After that, you lead the ticket all the way to
DECISION on your own, assigning work, validating, correcting, and moving between stages
without asking the owner to push it forward. Only a **genuine blocker** or **DECISION**
stops you. Never ask the owner to type "continue".

**Start the watchdog once, when autonomy begins**, right after
`non-functional-test/state.md` is created:

```bash
python3 <this-skill>/scripts/lead-watchdog.py \
  --ticket <ticket-dir> --interval 180 --idle 540 --detach
```

Confirm it started by reading `<ticket-dir>/non-functional-test/.watchdog.pid`. A second
launch is a no-op while one is running.

The watchdog is an external clock, not an employee. It only reads
`non-functional-test/state.md`. When an active stage has been quiet longer than the idle
window, it queues a short "validate and continue" message into your own session. It
never writes `state.md`, never decides a stage, and never ends the run. It exits by
itself at DECISION or BLOCKED.

## Before DEPLOY

If `non-functional-test/state.md` already exists, resume from it: run the control
loop from step 1, and trust only what that file records as done.

Otherwise, read Loop 1's `state.md` in the ticket directory. If it does not show the ticket as
COMPLETE, create `non-functional-test/state.md` at BLOCKED, quote that line, and stop.
Otherwise create `non-functional-test/` and copy `assets/templates/state.md` into it.

**Declare all four files before assigning anyone.** The run has one write declaration,
shared by you and every employee, so the first narrow declaration locks everyone else
out. Declare `state.md`, `test-plan.md`, `code-review.md`, and `verdict.md`, by full
path, together with `test-output/` and the watchdog's files. An employee never narrows
that declaration to its own file, and never writes a file this skill does not name.

## Staying in sync

- **One coordinator.** Only the Lead decides the next step and writes `state.md`.
- **One sync point.** Read `state.md` before every action and write it after.
- **One active state-changing assignment at a time.** Do not open the next one until the
  current result is back and checked.
- **No employee-to-employee handoffs.** All work flows employee → Lead → employee.

## The ticket directory

The skill runs against the same ticket directory Loop 1 used. It reads Loop 1's and
Loop 2's files and never writes to them. It writes only inside one new folder:

```text
<ticket-dir>/
  state.md, specification.md, code-review.md, ...   Loop 1 and Loop 2 — read only
  non-functional-test/
    state.md        the skill's state file — only the Lead writes it
    test-plan.md    the Test Plan — only the QA lead writes it
    code-review.md  the code review of the Test Plan — only the Judge writes it
    verdict.md      the QA lead's comments on the run — only the QA lead writes it
    test-output/    raw build and health output
```

Every file sits inside `non-functional-test/`, so nothing Loop 1 or Loop 2 wrote can be
overwritten, even where a name such as `state.md` or `code-review.md` is the same.

## The control loop

```text
1. READ    state.md — what stage, and the one unmet exit criterion?
2. DECIDE  the single smallest next action.
3. DO      assign one bounded task to an employee.
4. JUDGE   the real result — read the files the employee wrote, not its summary —
           then advance, stay, go back, or block.
5. WRITE   the outcome and next action into state.md, and append one History line
           naming the file you read and what it showed.
6. LOOP    back to 1 — in the same turn.
```

**You know everything because you read everything.** An employee's summary is a claim;
the file it wrote is the evidence. Accept only the file.

## Stages in detail

### DEPLOY

#### Repositories other than director2-aws

For repositories other than director2-aws, follow the deployment instructions in the
repository's root `AGENTS.md`.

- Assign the **SRE**. The SRE reads the repository's root `AGENTS.md` and follows its
  instructions to build the change, deploy it, and check its health. The SRE does not
  invent steps the `AGENTS.md` does not give. If the `AGENTS.md` has no deployment
  instructions, mark the run BLOCKED with that exact gap.
  - Run the build and deploy command the `AGENTS.md` gives, capturing its output to a
    file so the raw text survives past this step:

    ```
    <build and deploy command from AGENTS.md> > <ticket-dir>/non-functional-test/test-output/build.log 2>&1
    ```

  - Run the health check the `AGENTS.md` gives, and keep its raw output in
    `test-output/` for the Lead.
  - **Transient infra / interruption** (client disconnect, timeout) — **retry freely;
    it does not burn the 5-cap.** It is not a "stable problem"; nothing was learned
    and nothing was tried. If the same infra failure keeps recurring, that's a
    diagnosis worth reporting (why the environment won't hold), not a spent attempt
    budget.
  - **JUDGE before writing BLOCKED (control-loop step 4):** open `build.log` yourself
    and quote its actual tail in `state.md`. A description of the error ("the build
    failed because of X") is not evidence and does not satisfy this step — only the
    file's own text does. If you have not read `build.log`, you have not verified the
    failure.
- The services and databases the change needs must be ones this deployment brings up.
  If the change needs a service or database the deployment does not provide, mark the
  run BLOCKED with that gap; do not deploy an assumed environment.
- This stage is complete when the change is deployed and its health is confirmed by
  the `AGENTS.md` health check.
- Mark the run BLOCKED when a needed capability is genuinely unavailable, such as the
  build failing. That is not a reason to improvise around the `AGENTS.md` instructions.

#### director2-aws Repository

For the director2-aws repository, use the following steps. During DEPLOY, the SRE
builds the change and deploys it to the shared lower environment using
`docker-director2-deploy`. The SRE gives the Lead the deployment result and health
checks.

- Assign the **SRE**. Before they can build the change's image, they must first resolve
  `director2-aws-build` — the container the build runs inside — in this order. Check
  state with this exact command — no `-it`, no TTY needed, no other check invented:

  ```
  docker inspect --format="{{ .State.Running }}" director2-aws-build
  ```

  - `true` → running and valid → reuse it.
  - Errors (container not found) → absent → create it with the `buildenv` alias below.
    Keep that shell session open and run the build steps (below) inside it directly —
    an absent-case container is interactive and auto-removed the instant its shell
    exits (a dropped connection, a timeout, or a tool call ending destroys it and any
    build state in it), so do not exit the shell and try to `docker exec` into it from
    a separate step:

    Run it in a PTY-capable terminal session; the terminal invocation must allocate a
    TTY. `bash -ilc` alone does not allocate one.

    ```
    bash -ilc 'cd $HOME/src/director2-aws && buildenv'
    ```

    `server-build` image must already exist locally — this workflow never builds,
    pulls, publishes, or replaces it, and never rebuilds `server-build` to "fix" a
    build failure.
  - `false`, or running but not the configured image/mount → exists but stopped or
    invalid → stop with the exact blocker. Do not remove or replace the container, or
    invent another container path.

  **VERIFY:** quote this command's actual output in `state.md` before acting on it. A
  permissions error, a TTY error, or any other error from a *different* command you
  tried instead is not evidence about the container's state — rerun the exact command
  above and report what it, specifically, printed.
  - Once it's running, run this exact command inside it, capturing its output to a file
    so the raw text survives past this step:

    ```
    docker exec director2-aws-build bash -c \
      'cd /director2-aws/director2 && ./gradlew buildDockerImageLocally' \
      > <ticket-dir>/non-functional-test/test-output/build.log 2>&1
    ```

    This builds the changed service's image from the current code — the real build, not
    a rebuild-from-cache — and tags it `:latest` in the local Docker store, the exact
    image `docker-director2-deploy`'s CONFIG step picks up via
    `--director-version local`.

  - **Transient infra / interruption** (VPN drop, Nexus/Ryuk flake, buildenv container
    death, client disconnect, timeout) — **retry freely; it does not burn the 5-cap.**
    It is not a "stable problem"; nothing was learned and nothing was tried. If the
    same infra failure keeps recurring, that's a diagnosis worth reporting (why the
    environment won't hold), not a spent attempt budget.
  - **JUDGE before writing BLOCKED (control-loop step 4):** open `build.log` yourself
    and quote its actual tail in `state.md`. A description of the error ("the build
    failed because of X") is not evidence and does not satisfy this step — only the
    file's own text does. If you have not read `build.log`, you have not verified the
    failure.
- Only once that image is built does the SRE call `docker-director2-deploy`. The
  `--services` and `DB_DEPLOY_TYPE` values are the ones that run the changed code; the
  Engineer works them out from the change itself before the deploy, and the SRE uses
  those values and does not guess.

  **Confirmed operations**

  | Operation that runs the changed code | `--services` must include | `DB_DEPLOY_TYPE` must include |
  |---|---|---|
  | `disMediaCorePublishStream*` | `CIS` | `CIS` |
  | `contentSearch` | `router,data1,data2` | `router,data1,data2` |
  | code that reads the `router` database | `router` | `router` |
  | code that reads the `cis` database | `CIS` | `CIS` |

  For an operation not listed above, the Engineer analyzes it before the deploy. Do not
  infer its requirements from its name, endpoint, or a broad category: trace the
  request through router/configuration to its target and the downstream path the
  changed code sits on, and record every runtime service and every database that path
  needs.

  Union every applicable confirmed and analyzed row in both columns. If the route
  cannot be proven from code or configuration, assign the Senior Engineer to trace it;
  do not deploy an assumed environment.

  Before calling `docker-director2-deploy`, the Lead records that union in `state.md`
  and compares it with the actual `--services` and `DB_DEPLOY_TYPE` values.

- The docker-director2 lower environment is shared and is simply used as it is. This
  skill deploys one ticket's change into it and does not batch changes or tear the
  environment down.
- This stage is complete when the environment is up, the change is deployed, and its
  health is confirmed by the deploy skill's own HEALTH step.
- Mark the run BLOCKED when a needed capability is genuinely unavailable, such as the
  VPN being down or the image build failing. That is not a reason to improvise around
  the deploy skill.

**Lead check:** open the files in `test-output/` yourself and quote their end in
`state.md`. Only a successful build and a healthy deployment move the run to TEST PLAN.
A build failure goes to the Senior Engineer. A genuinely unavailable environment goes
to BLOCKED.

### TEST PLAN

Assign the **QA lead**. It writes `test-plan.md` from `assets/templates/test-plan.md`.

The Test Plan covers the non-functional requirements one at a time, with one section
for each.

#### Non-functional Requirements 1: performance anti-pattern detection

**What it reads:**

- the original ticket and Loop 1's frozen `specification.md`;
- the changed files listed in Loop 1's `04-code-guide.md` and `code-review.md`, reading
  their current code, because the change may already be committed;
- the code the change calls inside a loop, and the code that calls the changed code
  inside a loop, because a slow pattern can come from putting existing code inside a new
  loop;
- the repository's root `AGENTS.md`, and the deployed system.

**What it looks for.** Code whose work grows badly as its input grows. These patterns
are a place to start, not a closed list; the QA lead also reports any other pattern it
finds that makes the work grow badly with the input:

1. A loop inside a loop, where both loops go over input that can grow.
2. A database query, a remote call, or a file read inside a loop, so there is one call
   for every item.
3. The same costly work repeated for every item when it could be done once, such as
   building the same object, client, or pattern again and again.
4. Searching a list inside a loop, where a direct lookup would do.
5. Loading a whole table, file, or collection into memory when only part of it is
   needed.
6. A collection that keeps growing with no limit, and no paging.
7. Building a long string piece by piece inside a loop.
8. Waiting, sleeping, or retrying inside a loop.

**What it writes for each finding:**

- the file and line;
- which pattern it is;
- which input makes it grow, and where that input comes from, such as a request, the
  database, or a message;
- how the work grows: once per item, or once per item for every item;
- how large that input can really get in normal use, from the data, the domain, or the
  specification. A missing limit in the code does not make an input large;
- its **severity**, with the reason:
  - **critical:** the work grows very fast, such as once per item for every item, or a
    separate call for every item, and the input is large in normal use. One query that
    handles all the items at once is not a separate call for every item;
  - **high:** the work grows fast, and the input can get large in normal use;
  - **medium:** the work grows, but the input is usually small or has a limit;
  - **low:** the code is fine today, but would become a problem if the input grew.

A pattern whose input cannot grow, such as a loop over a fixed list of three items, is
not a finding. It is recorded as a note, with the reason.

When there is no finding, the Test Plan says what the changed code does and why nothing
in it grows with the input, with the file and line.

#### Non-functional Requirements 2: maintainability and readability

**What it reads:**

- the current code of the changed files, and the whole file each change sits in;
- two existing examples in the repository that do the same kind of job, to compare
  against;
- the repository's root `AGENTS.md`, and any conventions document it names.

**What it looks for.** Check the change against every rule the repository's root
`AGENTS.md` writes down, and record each rule the change touches as a finding or as a
note with the reason it holds. Then use the `clean-code-guardian` skill's checks as the
list of what else to look at. Two rules from this skill come first:

- Every finding cites a rule the repository wrote down, or an existing example the
  change departs from, with its file and line. A finding that cites neither is not a
  finding. `clean-code-guardian` is the list of what to look at; it is never the
  citation.
- Its fixed sizes, such as 50 lines for a function, are signals to look closer, not
  limits.

Write findings in this skill's format and severity, not `clean-code-guardian`'s verdict.

**What it writes for each finding:** the file and line, which check it is, what it
cites, what the next person would get wrong, and its severity with the reason:

- **critical:** the next change is likely to introduce a bug, such as the same rule in
  two places, or a name that says the opposite of what the code does;
- **high:** the code can only be understood after reading it several times;
- **medium:** the code is understandable, but departs from how the codebase does the
  same job;
- **low:** cosmetic, and nothing follows from it.

When there is no finding, the Test Plan says what the changed code does and which
example it was compared against, with the file and line.

**Lead check:** read `test-plan.md` yourself. Every finding has its file and line, its
pattern, its input, how it grows, and its severity with the reason. Every maintainability
finding has its file and line, its check, what it cites, and its severity with the
reason. A "no finding" has its reason. Only then move to CODE REVIEW.

### CODE REVIEW

Assign the code review to the **Judge**, independent, with a fresh context that never
saw the QA lead's reasoning. Give it the original ticket, Loop 1's `specification.md`,
the changed files and their current code, `test-plan.md`, and the full path of this
skill's `assets/templates/code-review.md`, which it must use.

The Judge reads the changed code **itself**, not only the Test Plan, and checks:

1. **Nothing is missed.** No slow pattern in the changed code, or in the code it calls
   or is called from inside a loop, is missing from the Test Plan, whether it is on the
   list of patterns or not.
2. **Every finding is true.** The pattern is at the file and line given, and the input
   and growth are described correctly.
3. **Every severity is right.** It follows from how the work grows and how large the
   input can get.
4. **Every note and "no finding" is true** against the code.
5. **Maintainability: nothing is missed, and every finding cites** a written rule or an
   existing example, at the file and line given. Every rule in the repository's root
   `AGENTS.md` that the change touches is recorded as a finding or a note.
6. **Maintainability: every severity is right.** It follows from what the next person
   would get wrong, not from preference.

The Judge writes `code-review.md` from `assets/templates/code-review.md`: one section
per round, appended and never rewritten. Each section has its verdict, APPROVED or
CHANGES NEEDED, and each problem found, with the file and line and what would fix it.
On a repeat round, it lists each earlier problem and whether it is now fixed.

**Exit:** first set the "Code review round" field in `state.md` to the number of the
round just read, whether it was APPROVED or CHANGES NEEDED. Then APPROVED moves the run
to RUN, and CHANGES NEEDED sends the Test Plan back to the QA lead, which fixes exactly
what the code review named. After 5 rounds on the same problem, go to BLOCKED. From RUN
onward, the Test Plan does not change.

### RUN

Assign the **QA lead**. Neither requirement has anything to run against
the service: the approved findings are the result. The QA lead writes `verdict.md` from
`assets/templates/verdict.md`, with every approved finding, its severity, and its file
and line, or the approved "no finding" with its reason. It copies them from the approved
`test-plan.md` and never changes them.

**Lead check:** read `verdict.md` yourself, and check that every finding in it matches
the approved `test-plan.md`.

### DECISION

This is your decision, not an automatic step. Read `test-plan.md`, `code-review.md`, and
`verdict.md`, and record **PASS** or **FAIL** in `state.md`, with the reason. The reason
names each finding and its severity that the decision rests on. No fixed rule decides
it: you weigh the findings and their severities.

### BLOCKED

Mark the run BLOCKED only after trying the safe options. Record the stage it came from
and the one exact action a human must take.

## Delegation is the model

You always delegate work through a short assignment: the exact inputs the employee may
read, the single deliverable, the files it may write (everything else is off-limits),
what "done" looks like, and whether it may run a command. The employee returns a result
with real evidence. You check it against the current state, then accept or reject it.

## When to use

Invoked manually, against one ticket that Loop 1 has completed, one ticket at a time.
It is not chained automatically to Loop 1 or Loop 2.

## Non-negotiables

- Read `state.md` before every action, and write it after.
- DEPLOY comes first. The Test Plan passes its code review before RUN.
- Only the Lead writes `state.md`. Only the QA lead writes `test-plan.md` and
  `verdict.md`. Only the Judge writes `code-review.md`.
- The Judge never does the code review of a Test Plan it wrote.
- Every finding has its file and line, and a severity with its reason.
- The Test Plan does not change after the code review approves it.
- Write only inside `non-functional-test/`. Never change a file Loop 1 or Loop 2 wrote.
- Never change the product code, the service's image, or its startup settings.
- One active state-changing assignment at a time.
- Never put a secret in a ticket file, prompt, or command argument.
- **The Lead's hand never touches `test-plan.md`, `code-review.md`, or `verdict.md`.**
  If an employee's write is blocked, for example because the declaration does not list
  the file as writable, that is a setup gap to fix: add the file to the run's writable
  set and let the employee write it. Never write the employee's file yourself. A
  blocked write that cannot be granted is BLOCKED.
- **All four files are declared once, before the first assignment**, and no employee
  narrows that declaration or writes a file this skill does not name.
- **A stalled employee is a failed delegation.** Reissue the same bounded assignment
  to a fresh employee; never do its work yourself. A temporary environment problem or
  interruption does not count toward the 5-attempt limit. A substantive failure, where
  the employee tried and the result is wrong, empty, or unworkable, counts as one
  attempt.
- **When debugging is needed, assign the Senior Engineer.** Do not debug yourself, do
  not block, and do not ask the owner. Act on its diagnosis.
- Use `docker-director2-deploy` for deployment in director2-aws. Do not run
  `local-up.sh` or Docker commands yourself. For other repositories, follow the
  deployment instructions in the repository's root `AGENTS.md`.

## Verification

- `non-functional-test/state.md` exists, its stage is one of the stages above or
  BLOCKED, and its History is append-only, with one line after every action.
- The build and health output is in `test-output/` before TEST PLAN started.
- For director2-aws, `state.md` records the `--services` and `DB_DEPLOY_TYPE` values
  and how they were worked out before `docker-director2-deploy` was called, and the
  DEPLOY record includes its health-check output.
- `code-review.md` has an APPROVED round before RUN started.
- Every performance finding in `test-plan.md` and `verdict.md` has its file and line,
  its pattern, its input, how it grows, and its severity with the reason. Every
  maintainability finding has its file and line, its check, what it cites, and its
  severity with the reason.
- `state.md` records PASS or FAIL with the reason, naming the findings it rests on.
