# SPECS Guide (AVOD method, embedded)

This is the `avod-ticket` Stages 1–4 method, embedded here because it works.
**Follow it as written — do not substitute your own style, reorder, or paraphrase.**
Stages 5–6 of avod (implement, report) are replaced by this workflow's
TDD → JUDGE → MUTATION.

**Key rules — never break these:**
- Stages 1–3 produce documents. No code until the roadmap (Stage 3) is approved.
- Stage 2 quotes real code with file paths and line numbers. No prose summaries. No guesses.
- The test is always Step 1 of the roadmap, written before any implementation.
- Code review is always a named roadmap step.
- Ask few, investigate deeply — a question with your best guess, not an interrogation.

## Setup — detect repo and test strategy

Detect the repo and set the test strategy for all stages:
- `run-harness-sidecar.sh` present → **director2-aws** (harness XML tests)
- `dmedia/` + `build.gradle` → **dmedia** (`./gradlew test`; `./gradlew runHarnessTests`)
- `build.gradle`, no harness → **Spring Boot / Gradle** (`./gradlew test` + `@SpringBootTest`)
- `pom.xml`, no harness → **Spring Boot / Maven** (`mvn test` + `@SpringBootTest`)

Tell the owner what was detected. Ask where to save the docs (default: the ticket dir).

## Stage 1 — Ticket Intake → `01-scope.md`

**Goal:** understand exactly what "done" means before reading a line of code.

Get the ticket (pasted text or a reference). Read it, then ask the **five clarifying
questions, each with your best guess so the owner usually just confirms**:

1. **Which repo** owns this change? (your guess from the ticket)
2. **What kind of change** — bug fix / behavior change / new feature / config? (guess)
3. **What does "done" look like** from the API/behavior perspective? (guess)
4. **Constraints** — backward-compatible / no config / deploy order / modules not to touch / none.
5. **Prior context** — related ticket, investigation, thread, or known code location.

Only genuine business/scope decisions need a real answer; anything the code can
answer, investigate in Stage 2 — don't ask it. Then write the scope statement
(Ticket / Repo / Type / Goal / Done-when / Constraints / Prior context / Out of scope).

**Gate:** explicit "yes" on the scope. Do not read code until this passes. Save `01-scope.md`.

## Stage 2 — Investigation → `02-investigation.md`

**Goal:** map the current state of the code. Quote real blocks with line numbers. No guesses.

Produce the document in this exact format:

- `**What the ticket is asking:**` one sentence (the North Star).
- `## Current behavior` — for each file that changes: `### File.java:start–end`, a
  fenced block of the **actual quoted code**, then one sentence on what is wrong/missing.
- `## What already exists to reuse` — `### Helper.java:line` + quoted code; "use in
  [location] — do not write a new implementation."
- `## Where the change lives` — a table: File | Lines | What changes.
- `## What is missing` — the specific code/test that does not yet exist, stated precisely.
- `## Open questions` — anything blocking the plan; else "None".

**Quality bar — not done until:** every reference verified by reading the actual
file; Current behavior quotes **real code**, not prose (a line number alone is not a
quote); the table shows actual line numbers; reuse quotes the exact helper; no
"probably / I think / likely / should be"; open questions explicit. **Do not design
the fix here.**

**Gate:** developer confirms it is accurate and complete. Save `02-investigation.md`.

## Stage 3 — Roadmap → `03-roadmap.md`

**Goal:** a step plan with done-criteria; approved before any code.

- `# Plan: [title]` / **North Star** / **Ticket** / **Overall:** next
- `## Steps` — table: # | Step | File(s) | Done when | Status
  - 1: write the failing test → RED
  - 2: implement the smallest change (name the method) → GREEN
  - 3: run the suite → no new failures
  - 4: code review → passes
  - (verify + mutation are this workflow's JUDGE and MUTATION stages)
- `## Risks` — table: Risk | Caught by.

Rules: **Step 1 is always the failing test, before implementation; Step 4 is always
code review.** For **director2-aws** the test is a harness XML test — its execution
is the `director2-harness-test` skill's job; do not describe harness steps here.

**Gate:** developer approves the plan. No code before this. Save `03-roadmap.md`.

## Stage 4 — Code Guide + Test Plan → `04-code-guide.md`

- **Code Change Guide:** Files to change (table) / Pattern to follow (quote the exact
  helper/method from Stage 2) / What NOT to change (scope-creep guard) / Config changes.
- **Test Plan:** cases with inputs + expected outputs — harness XML cases for
  director2-aws; `@SpringBootTest`/unit for Spring Boot. Written before code.

Save `04-code-guide.md`. No gate — feeds TDD.

## Gherkin → `specification.md`

The approved behavior as **Gherkin scenarios** + done criteria — the contract TDD
implements and the judge reviews. Record the honest RED strategy.

## Approval — SPECS exit

Show the owner the package; get approval. Then the lead runs autonomously to the end.
