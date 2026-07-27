---
name: avod-ticket
description: AVOD team workflow from Jira ticket to merged, tested code. Six gated stages — intake, investigation, roadmap, code guide, implement+verify, completion report. Enforces harness-first for director2-aws, Gradle harness tests for dmedia, Spring Boot integration tests for other repos. All AVOD domain knowledge embedded. No stage is skipped. Code is not written until Stage 3 is approved. Generates PR description document for developer/reviewer use.
allowed-tools: AskUserQuestion, Read, Write, Bash
---

# AVOD Ticket to Delivery

## Overview

Take an AVOD Jira ticket from raw description to merged, verified code. Six stages. Every stage produces a document or a verified result. Code is not written until Stage 3 is approved by the developer.

```
INTAKE ──→ INVESTIGATION ──→ ROADMAP ──→ CODE GUIDE ──→ IMPLEMENT ──→ REPORT
  │              │               │            │              │            │
  ▼              ▼               ▼            ▼              ▼            ▼
5 questions   Real code       Living      Test plan      Red→Green    AI-attributed
answered      quoted          plan        pre-written    suite clean   record
```

**Key rules — never break these:**
- Stages 1–3 produce documents. No Java or code changes until Stage 3 is approved.
- Stage 2 quotes real code with file paths and line numbers. No prose summaries. No guesses.
- The roadmap (Stage 3) is a living document — update step statuses as work progresses.
- Harness test is always Step 1 (director2-aws). Written before any implementation.
- Code review is always a named roadmap step. Never implicit.
- A ticket is done only when every roadmap step is marked `done`.

## When to Use

- Developer has an AVOD Jira ticket and needs to go from understanding to merged code
- Repos: `director2-aws`, `dmedia`, `moneyball-aws`, `fw-catalogsync-aws`, or any other AVOD team repo
- Developer can provide the ticket as pasted text or as a URL/reference to fetch

**When NOT to use:** A one-line fix, a config-only change, or work where scope is already fully understood and a plan already exists.

---

## Setup: Detect Repo and Test Strategy

**Before starting Stage 1**, detect which repo you are in and set the test strategy for all stages.

Run this check:
```bash
pwd && ls build.gradle pom.xml run-harness-sidecar.sh 2>/dev/null
```

**Decision table:**

| What you find | Repo type | Test strategy |
|---------------|-----------|---------------|
| `run-harness-sidecar.sh` exists | `director2-aws` | Harness XML tests via `./run-harness-sidecar.sh` |
| `dmedia/` in path + `build.gradle` exists | `dmedia` | Gradle tests: `./gradlew test` (unit); Harness tests: `./gradlew runHarnessTests` (Java/TestContainers) |
| `build.gradle` + no harness script | Spring Boot / Gradle | `./gradlew test` + Spring Boot integration tests (`@SpringBootTest`) |
| `pom.xml` + no harness script | Spring Boot / Maven | `mvn test` + Spring Boot integration tests |
| Neither | Unknown | Ask the developer: "What test command does this repo use?" |

Tell the developer what was detected before starting:
```
✓ Detected: director2-aws (harness)
  Test command: ./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<name>.xml
  Suite command: ./run-harness-sidecar.sh -p -m -t 10 <module>
```
or:
```
✓ Detected: dmedia (Gradle + harness)
  Test command: ./gradlew test (unit tests, excludes harness)
  Harness command: ./gradlew runHarnessTests (Java integration tests with TestContainers)
```
or:
```
✓ Detected: Spring Boot repo (Gradle)
  Test command: ./gradlew test
  Integration tests: @SpringBootTest — run via ./gradlew integrationTest or equivalent
```

Store the detected repo type and commands — use them in every stage that references test or build commands.

### Ask for the output directory

After reporting the detected repo, ask:

> "Where should I save all workflow documents (scope, investigation, roadmap, code guide, implementation log, pull-request, completion report)?
> Press Enter to use the current directory (`[show the result of pwd]`), or type a path."

- If the developer provides a path → use that as OUTPUT_DIR. Create it if it does not exist.
- If the developer presses Enter or says nothing → OUTPUT_DIR = current working directory (the repo root).

Tell the developer: "✓ Documents will be saved to: [OUTPUT_DIR]"

Use OUTPUT_DIR for every file written in every stage. Never hardcode a subdirectory — always write to wherever the developer chose.

---

## Stage 1 — Ticket Intake

**Goal:** Understand exactly what "done" means before reading a single line of code.

### Get the ticket

Ask the developer: "Paste your Jira ticket (type END on a new line when done), or give me a URL or ticket ID and I'll look it up."

- If they paste text → read everything until END
- If they give a URL or ID → use it to fetch the ticket content

### Ask the five clarifying questions

Read the ticket, then use the **AskUserQuestion tool** to ask these questions with dropdown selections.

**Question 1: Which repo owns this change?**

Use AskUserQuestion tool:
- header: "Repo"
- question: "Which repo owns this change? (Based on ticket, I'm guessing [your guess based on content])"
- options:
  - director2-aws (Harness XML tests via ./run-harness-sidecar.sh)
  - dmedia (Spring Boot + Java harness tests via ./gradlew test / runHarnessTests)
  - moneyball-aws (Spring Boot / @SpringBootTest via ./gradlew test)
  - fw-catalogsync-aws (Spring Boot / @SpringBootTest via ./gradlew test)
  - Other (I'll specify the repo and test command)

**Question 2: What kind of change is this?**

Use AskUserQuestion tool:
- header: "Change type"
- question: "What kind of change is this? (Based on ticket, I'm guessing [your guess])"
- options:
  - Bug fix (Code is broken, not doing what it should)
  - Behavior change (Intentional logic change affecting existing behavior)
  - New feature (Adding something that didn't exist before)
  - Config change (Configuration-only, no code logic changes)

**Question 3: What does "done" look like?**

Use AskUserQuestion tool:
- header: "Done when"
- question: "What does 'done' look like from the API perspective? (My guess: [your guess])"
- options:
  - Your guess is correct
  - Let me describe it differently

If they choose "Let me describe it differently", ask a follow-up free-text question.

**Question 4: Are there constraints?**

Use AskUserQuestion tool:
- header: "Constraints"  
- question: "Are there constraints I should know about?"
- multiSelect: true
- options:
  - Must be backward-compatible
  - No config changes allowed
  - Must deploy to INT before PROD
  - Must not touch certain modules
  - No constraints

**Question 5: Is there prior context?**

Use AskUserQuestion tool:
- header: "Prior context"
- question: "Is there prior context — related ticket, investigation doc, Slack thread, or known code location?"
- options:
  - Yes, I'll provide details
  - None that I know of

### Write the scope statement

After all five questions are answered, write:

```
SCOPE STATEMENT
───────────────
Ticket:       [ID and title]
Repo:         [director2-aws / dmedia / moneyball-aws / fw-catalogsync-aws / other]
Type:         [new feature / behavior change / bug fix / config]
Goal:         [One sentence — what we are building and why]
Done when:    [Specific, testable condition from question 3]
Constraints:  [From question 4, or "None stated"]
Prior context:[From question 5, or "None"]
Out of scope: [Anything explicitly excluded]
```

Then use AskUserQuestion tool for confirmation:
- header: "Scope OK?"
- question: "Does this scope look right?"
- options:
  - Yes, save and proceed to Stage 2
  - No, something's wrong
  - Refine, show me what to change

**Gate:** Explicit "yes" on the scope statement. Do not read any code until this gate passes.

- **Yes** → save to `[OUTPUT_DIR]/01-scope.md`, proceed to Stage 2
- **No** or **refine** → ask what's wrong, update, show again

---

## Stage 2 — Investigation Document

**Goal:** Map the current state of the code. Quote real blocks with line numbers. No guesses.

### What to investigate

Based on the scope statement, identify the relevant files. For director2-aws this typically means:
- The Op class that needs changing (in `suite/<module>/src/`)
- Existing helpers or patterns to reuse
- The test file location (in `suite/<module>/test/`)

Use AskUserQuestion tool:
- header: "Start files"
- question: "Which files should I start with? (My guess: [your guess based on ticket])"
- options:
  - Your guess is correct, start there
  - Let me specify different files

Read each file the developer names (or your guess if they confirm). Then follow imports, references, and usages to find related files. Use Read to open and quote the actual code.

### Investigation document format

Produce a document in this exact format:

```markdown
# Investigation: [ticket title]

**What the ticket is asking:** [One sentence. The North Star for everything that follows.]

## Current behavior

For each file that will change, quote the relevant block and explain what is wrong or missing:

### [FileName.java]:[start line]–[end line]

```java
[exact quoted code from the file]
```

[One sentence explaining what is wrong or missing here.]

## What already exists to reuse

For each helper, utility, or pattern that the implementation should use:

### [HelperName.java]:[line]

```java
[exact quoted code]
```

Use this in [location] — do not write a new implementation.

## Where the change lives

| File | Lines | What changes |
|------|-------|-------------|
| [path/to/File.java] | [N–M] | [Specific description] |
| [path/to/test.xml or TestClass.java] | new / [N–M] | [New test or modified test] |

## What is missing

[The specific code or test that does not yet exist, stated precisely. Not "we need a check" — "we need a null check on `authUserId` before calling `isAvodAnonymousSession()` at line 67 in `SomeOp.java`".]

## Open questions

[Anything requiring a decision before Stage 3 starts. These block the plan until resolved. If none, write "None".]
```

### Quality bar — the investigation is not done until:

- Every file and method reference has been verified by reading the actual file — no guesses
- The "Current behavior" section quotes real code, not prose descriptions
- The "Where the change lives" table shows actual line numbers
- The "What already exists to reuse" section quotes the exact helper or pattern
- No sentence contains "probably", "I think", "likely", or "should be"
- Open questions are listed explicitly, not buried in prose

Then use AskUserQuestion tool for confirmation:
- header: "Investigation OK?"
- question: "Does this investigation look accurate?"
- options:
  - Yes, save and proceed to Stage 3
  - No, something's missing or wrong
  - Refine, show specific issues
  - Back, return to Stage 1

**Gate:** Developer confirms the investigation is accurate and complete.

- **Yes** → save to `[OUTPUT_DIR]/02-investigation.md`, proceed to Stage 3
- **No** or **refine** → ask what's wrong, investigate further, update
- **Back** → return to Stage 1

---

## Stage 3 — Roadmap (Living Plan)

**Goal:** A step-by-step plan with specific done-criteria. Developer approves before any code is written.

### Generate the roadmap

Using the scope from Stage 1 and investigation from Stage 2, generate the roadmap in this format:

```markdown
# Plan: [ticket title]

**North Star:** [One sentence from scope statement]
**Ticket:** [Jira ID]
**Overall:** next

## Steps

| # | Step | File(s) | Done when | Status |
|---|------|---------|-----------|--------|
| 1 | [Write test — see harness or Spring Boot rules below] | [test file path] | [test command] → RED (failing, expected) | next |
| 2 | [Implement the change — be specific, name the method] | [impl file path] | [same test command] → GREEN | next |
| 3 | Run full suite | [module or test dir] | [suite command] → no new failures | next |
| 4 | Code review | PR diff | All AVOD checklist items pass (see Stage 5) | next |
| 5 | Merge + verify | master / main | PR merged; [INT or staging] confirms expected behavior | next |

## Risks

| Risk | Caught by |
|------|-----------|
| [What could break] | [Which step surfaces it] |
```

**Harness rule (director2-aws):**
Step 1 is always a harness XML test. It must be written before any Java changes. The done-when for Step 1 is: `./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<name>.xml` returns RED (failing). A plan without this step is not approved.

**Harness rule (dmedia):**
Step 1 is a failing harness test (Java JUnit test with TestContainers). It must be written before any implementation changes. The done-when for Step 1 is: `./gradlew runHarnessTests --tests "*.TestClassName"` returns RED (failing). A plan without this step is not approved.

**Spring Boot rule (other repos):**
Step 1 is a failing integration test or unit test written before any implementation. Done-when: `./gradlew test` or `mvn test` returns RED. If the repo supports `@SpringBootTest` end-to-end tests, prefer those for the acceptance case.

**Code review rule (all repos):**
Step 4 is always code review. It uses the AVOD checklist in Stage 5. The plan is not done until this step is marked `done`.

### Gate checklist

Before asking the developer to approve, verify:
- [ ] Every step has a specific "done when" — not "code is written" but "test passes" or "checklist passes"
- [ ] Every risk names which step catches it
- [ ] Step 1 is always the test (harness or integration), written before implementation
- [ ] Step 4 is always code review with the AVOD checklist
- [ ] No step is vague ("implement the feature" — be specific about the method and file)

Then use AskUserQuestion tool for confirmation:
- header: "Plan OK?"
- question: "Does this plan look right?"
- options:
  - Yes, save and proceed to Stage 4
  - No, something's wrong with the plan
  - Refine, show me what to change
  - Back, return to Stage 2

**Gate:** Developer explicitly approves the plan. No code is written before this gate passes.

- **Yes** → save to `[OUTPUT_DIR]/03-roadmap.md`, proceed to Stage 4
- **No** or **refine** → ask what's wrong, update the plan, show again
- **Back** → return to Stage 2

---

## Stage 4 — Code Guide + Test Plan

**Goal:** Exact instructions for what to change and what tests to write. No gate — feeds directly into Stage 5.

### Code Change Guide

```markdown
## Code Change Guide: [ticket title]

### Files to change

| File | What changes |
|------|-------------|
| [path/to/File.java] | [Exact description — e.g., "add null check on authUserId before calling isAvodAnonymousSession() at line 67"] |
| [path/to/test file] | [New test cases — reference the test plan below] |

### Pattern to follow

[Reference the specific existing file and method from Stage 2 investigation. Quote it again here.
Example: "Follow `AccountMapDef.isAvodAnonymousSession()` at line 41 — use this exact helper, do not write a new check."]

### What NOT to change

[Files that look related but must not be touched in this ticket. Prevents scope creep.
Example: "Do not touch `ZoltarScoringOp.java` — it is unrelated to session identity."]

### Config changes

[If any director-config or application.yml key must be added or changed, name it here and say which environment to deploy to first. If none, write "None required."]
```

### Test Plan

Written before any code changes. Be specific about inputs and expected outputs.

**For director2-aws (harness XML):**
```markdown
## Harness Test Plan: [ticket title]

Test file: suite/<module>/test/test-<operationName>.xml

| Case name | Input fields | Expected output | Mode |
|-----------|-------------|-----------------|------|
| happy-path-[scenario] | [specific input values] | [specific response fields and values] | exact |
| error-[missing-field] | [missing or invalid input] | [error response] | exact |
| edge-[boundary-case] | [boundary value] | [expected behavior] | subset |

Setup needed:
- [fakeAdvertContentDefinitionCreate for content ID X — makes title AVOD-eligible]
- [<now> locked to YYYY-MM-DD HH:MM:SS if time-sensitive]
- [SQL fixture for Y if no fake-create op exists]
```

**For Spring Boot repos (integration tests):**
```markdown
## Integration Test Plan: [ticket title]

Test class: [path/to/SomeServiceIT.java or SomeControllerTest.java]

| Test method | Setup | Input | Expected | Type |
|-------------|-------|-------|----------|------|
| [testHappyPath_scenario] | [DB state, mocks needed] | [request body or method args] | [response or state change] | @SpringBootTest |
| [testError_missingField] | [minimal setup] | [invalid input] | [exception or error response] | unit |
| [testEdge_boundaryCase] | [specific state] | [boundary value] | [expected behavior] | integration |

Notes:
- [Any TestContainers, H2, WireMock setup needed]
- [Transactional rollback or explicit cleanup required?]
```

Save both documents to `[OUTPUT_DIR]/04-code-guide.md`.

Tell the developer: "Guide and test plan saved. No gate — proceed to Stage 5 when ready."

Proceed directly to Stage 5.

---

## Stage 5 — Implement + Verify

**Goal:** Red → green → suite clean → code review passed → committed.

Work through this sequence in order. Update the roadmap step statuses as each step completes.

### Step 1: Write the test first

Remind the developer: "Write the test file now, before touching any implementation code."

**director2-aws:** Write the harness XML test file at the path named in the test plan. Run it:
```bash
./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<test-name>.xml
```
Expected result: RED (failing). If it passes immediately, the test is wrong — it is testing something that already works, not the new behavior.

**dmedia:** Write the harness integration test (Java JUnit class extending DMediaIntegrationTestBase) at the path named in the test plan. Run it:
```bash
./gradlew runHarnessTests --tests "*.SomeHarnessTest"
```
Expected result: RED (failing). If it passes immediately, the test is wrong.

**Spring Boot repos:** Write the integration or unit test at the path named in the test plan. Run:
```bash
./gradlew test --tests "com.example.SomeServiceIT"
# or
mvn test -Dtest=SomeServiceIT
```
Expected result: RED.

When the test is written and failing, update Step 1 in the roadmap to `done`.

### Step 2: Implement the change

The developer makes the Java or code change following the Code Change Guide from Stage 4.

**director2-aws:** After each iteration, use AskUserQuestion tool:
- header: "Build harness"
- question: "How would you like to build the harness?"
- options:
  - Manual (You run buildenv steps yourself - full control, good for debugging)
  - Automated (I run buildenv for you - hands-off)
  - Skip (Use existing image - fast iteration, may fail if image is stale)

**If manual:**
1. Start the build environment:
   ```bash
   buildenv
   ```
2. Inside the container, navigate to the module directory and compile:
   ```bash
   cd <module-directory>
   ./gradlew clean build -PdisableRyuk
   ```
3. Create the harness image:
   ```bash
   ./build-harness-mysql-image.sh
   ```
4. Exit the container and run the specific test from the host:
   ```bash
   ./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<test-name>.xml
   ```

**If you choose 2 (Automated):**
Skill will execute buildenv, compile, create the image, and run the test — you can monitor or step away.

**If you choose 3 (Skip):**
Run the test with the existing image:
```bash
./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<test-name>.xml
```
Note: This may fail if the harness image is stale. Rebuild using option 1 or 2 if needed.

When the test passes (GREEN), update Step 2 in the roadmap to `done`.

**dmedia:** Run:
```bash
./gradlew runHarnessTests --tests "*.SomeHarnessTest"
```

When the test passes (GREEN), update Step 2 in the roadmap to `done`.

**Spring Boot repos:** Run:
```bash
./gradlew test --tests "com.example.SomeServiceIT"
```

When the test passes (GREEN), update Step 2 in the roadmap to `done`.

### Step 3: Run the full suite

**director2-aws:**
```bash
./run-harness-sidecar.sh -p -m -t 10 <module>
```

**dmedia:**
```bash
./gradlew test              # unit tests (excludes harness)
./gradlew runHarnessTests   # full harness integration suite (Java/TestContainers)
```

**Spring Boot repos:**
```bash
./gradlew test
# or for full integration suite if available:
./gradlew integrationTest
```

#### Full suite results — handling failures

If **clean** (no failures):
→ update Step 3 to `done`, proceed to Step 4

If **failures found**:
Show the failures with test names and error details, then use AskUserQuestion tool:
- header: "Failures"
- question: "Which best describes these failures?"
- options:
  - Pre-existing (Test fails on main branch too - you'll verify this now)
  - Fix now (Fix the root cause; re-run suite until clean)
  - Separate ticket (File new Jira ticket for the collateral damage)
  - Skip (Requires explicit acknowledgment in code review)

**If pre-existing:**
1. Confirm by checking the test on main/master branch WITHOUT your changes:
   ```bash
   git stash
   ./run-harness-sidecar.sh -p -m -t 10 <module>
   git stash pop
   ```
2. If the test fails on main too → confirmed pre-existing ✓
3. Document in roadmap Step 3: "Suite has [N] pre-existing failures: [test names]"
4. Mark Step 3 as `done`

**If fix now:**
- Investigate the failing test(s)
- Fix the root cause in your implementation or the broken test
- Re-run the full suite
- Loop back to Step 3 until all new failures are resolved

**If separate ticket:**
- Document which tests failed and suspected root cause
- Create a follow-up Jira ticket to fix the underlying issue
- Document in roadmap: "Collateral damage — separate ticket [ID] filed for [tests]"
- Mark Step 3 as `done` with this caveat

**If skip:**
- Document in roadmap: "Suite fails on [tests]; developer chose not to fix"
- Mark Step 3 as `partial` with full details of failures
- This path requires developer's explicit confirmation in code review (Step 4)
- Note: Cannot merge without acknowledgment in code review

**Final gate for Step 3:**
Step 3 is marked `done` ONLY when:
- Suite is fully clean, OR
- All failures are confirmed pre-existing AND documented in roadmap, OR
- Developer chose option 3 (separate ticket) with ticket ID documented, OR
- Developer chose option 4 (skip) with explicit acknowledgment (to be verified in Step 4)

### Step 4: Code review — AVOD checklist

Run the following checklist against the diff. Every item must pass before Step 4 is marked `done`.

**First:** Invoke the `code-review-and-quality` skill for the general six-axis review (correctness, readability, architecture, security, performance, resource leaks). This catches issues not specific to AVOD domain.

**Then:** Apply this AVOD-specific checklist:

```
AVOD Code Review Checklist
──────────────────────────
Authentication & session:
- [ ] authUserId: every code path checks for null before using it
- [ ] Anonymous sessions handled separately from authenticated sessions
- [ ] AVOD-eligible sessions handled separately from non-AVOD sessions
- [ ] Non-AVOD users: behavior is completely unchanged

Redis:
- [ ] TTL is set explicitly and intentionally — no unbounded entries
- [ ] No stale cache entries possible after the change
- [ ] Redis key naming follows existing conventions in the module
- [ ] Redis client is NOT created per-request (use singleton/pooled — see resource-leak-detection skill)

Tests:
- [ ] Happy path covered
- [ ] Error case covered (missing field, null input, invalid state)
- [ ] Edge case covered (boundary value, session transition)
- [ ] No hardcoded user IDs, content IDs, or session tokens
- [ ] Test setup uses fake-create ops or TestContainers — no production data

Code quality:
- [ ] No new helper reimplements something that already exists (check Stage 2 reuse section)
- [ ] Pattern matches the closest existing Op or service in the same module
- [ ] No accidental scope creep — only the files named in Stage 4 are changed
- [ ] Config changes (if any) are deployed to INT before PROD
- [ ] No resources created per-request without cleanup (connections, clients, thread pools)

Harness suite status (director2-aws only):
- [ ] Step 3 full suite is clean OR pre-existing failures are documented with confirmation
- [ ] If new failures found (collateral damage):
  - [ ] Root cause of collateral damage identified or marked "unknown"
  - [ ] Separate ticket filed (if not fixing in this PR)
  - [ ] Developer acknowledges trade-off and impact
```

Show the checklist, then ask:

```
Does the code review pass? Yes / no?
```

- **Yes** → update Step 4 to `done`
- **No** → ask which items failed, let the developer fix them, re-run the checklist

**Special case — collateral damage found in Step 3:**
If Step 3 found new failures and developer chose "separate ticket" or "skip", add to the code review:
- Developer must explicitly acknowledge: "I understand this PR introduces collateral damage in [tests]; [separate ticket/acceptance] planned."
- Update checklist item: "Collateral damage acknowledgment: YES"
- Without this acknowledgment, Step 4 cannot be marked `done`.

### Step 5: Commit and merge

**Pre-merge verification gate:**
Before the PR can merge, confirm ALL THREE of these:

1. **Test status:** Step 2 → `done` (implementation test passes GREEN)
2. **Suite status:** Step 3 → `done` (suite clean OR failures confirmed pre-existing OR collateral damage acknowledged)
3. **Review status:** Step 4 → `done` (code review passed, including collateral damage acknowledgment if applicable)

If ANY step is not marked `done`, stop and ask the developer to fix it. Do not proceed to commit.

```
Ready to commit? Yes / no?
```

- **Yes** → run `git add` on the changed files, then `git commit`. Show the commit hash.
- **No** → pause and wait

After commit, ask:

```
PR opened and merged? Yes / no?
```

If yes, ask:

```
Has INT/staging confirmed expected behavior? Yes / waiting / not deployed yet?
```

- **Yes** → update Step 5 to `done`, update Overall to `done`, proceed to create pull-request document
- **Waiting** or **not deployed yet** → wait for confirmation before closing

Save `[OUTPUT_DIR]/05-implementation-log.md` with:
- Test result (RED/GREEN)
- Suite result (clean / pre-existing failures confirmed / new failures handled)
- Code review result (checklist items, any that needed fixing, collateral damage acknowledgment if any)
- Commit hash
- Merge status and INT confirmation

### Create Pull Request Document

After Step 5 is done and the PR is merged, generate the pull-request document that developers will use to describe the changes:

```markdown
# PR: [Jira ID] — [Short title]

## Title

```
[Jira ID]: [One-line description of what changed]
```

---

## Description

### Root cause

[If this is a bug fix, explain the root cause. Quote relevant code or database schema that explains why the issue occurred. Be specific — reference table names, column types, query patterns.]

[If this is a new feature, explain what capability was missing and why it's needed.]

### Fix

[Describe the solution in 1-3 sentences. If it's a simple change, show the before/after code snippet.]

Example:
```java
// Before:
.createFunc("group_concat(? ORDER BY ? SEPARATOR ' ')", ...)

// After:
.createFunc("group_concat(DISTINCT ? ORDER BY ? SEPARATOR ' ')", ...)
```

### Files changed

| File | Change |
|------|--------|
| [path/to/File.java] | [One sentence describing what changed in this file] |
| [path/to/TestFile.java] | [New test / modified test — what it verifies] |
| [path/to/fixture.sql] | [Test fixture if applicable] |

---

## Test Plan

**Test class:** [TestClassName] or [test-filename.xml]
**Method/Case:** [specific test method or case name]

[Step-by-step description of how the test verifies the fix or new feature:]

1. [Setup step — what data/state is created]
2. [Action step — what operation is triggered]
3. [Assertion step — what is verified]

[Include the test command:]
```bash
[command to run the test — e.g., ./run-harness-sidecar.sh or ./gradlew test]
```

---

## Notes

[Any important context for reviewers:]
- [Items explicitly out of scope]
- [Known limitations or future work]
- [Deployment order if relevant (INT before PROD, etc.)]
- [Related tickets or dependencies]
```

Save to `[OUTPUT_DIR]/06-pull-request.md`.

Tell the developer: "✓ Pull request document saved to `06-pull-request.md`."

Proceed to Stage 6.

**Gate:** All five roadmap steps marked `done` before merge.

---

## Stage 6 — Completion Report

**Goal:** AI-attributed, honest record of what happened. Matches what was planned vs. what actually occurred.

Generate the completion report in this format:

```markdown
# Completion Report: [ticket title]

**Ticket:** [Jira ID and title]
**Repo:** [director2-aws / dmedia / moneyball-aws / fw-catalogsync-aws]
**Date:** [today]
**Status:** Done — merged and verified

---

## What the AI Did (Skill-attributed)

**Stage 1 — Ticket Intake:**
- Read ticket, asked 5 clarifying questions
- Produced scope statement (saved to 01-scope.md)

**Stage 2 — Investigation:**
- Read [list the files that were actually read]
- Quoted [FileName.java]:[lines] — identified [specific finding]
- Quoted [HelperName.java]:[line] — identified existing reuse opportunity
- Produced investigation document (saved to 02-investigation.md)

**Stage 3 — Roadmap:**
- Generated 5-step plan with done-criteria
- Developer approved before any code was written (saved to 03-roadmap.md)

**Stage 4 — Code Guide + Test Plan:**
- Identified exact files to change: [list]
- Pre-wrote [N] test cases before implementation (saved to 04-code-guide.md)

**Stage 5 — Code Review:**
- Ran AVOD checklist: [N] items — all passed / [N] required fixes
- [Note any checklist item that initially failed and what was fixed]

---

## What the Developer Did

- Wrote [test file name] (red first)
- Implemented [specific method/class changes]
- Chose buildenv option: [manual / automated / skipped]
  - If manual: [buildenv steps completed without error / error details]
  - If automated: [skill completed buildenv steps / error details]
  - If skipped: [reason; harness image status]
- Ran full suite — [clean / N pre-existing failures confirmed / N new failures found and handled]
- Confirmed code review passed (including collateral damage acknowledgment, if applicable)
- Opened and merged PR [PR link or number if available]
- Confirmed [INT / staging] behavior

---

## Plan vs. Actual

| Step | Planned | Actual | Deviation |
|------|---------|--------|-----------|
| 1 | Write harness test | [done / details] | [None / reason] |
| 2 | Implement change | [done / details] | [None / reason] |
| 3 | Full suite clean | [done / details] | [None / reason] |
| 4 | Code review passed | [done / details] | [None / reason] |
| 5 | Merged + verified | [done / details] | [None / reason] |

---

## Harness Build & Suite Decisions (director2-aws only)

**Build option chosen:** [manual / automated / skipped]

If automated buildenv:
- buildenv setup: [successful / failed — reason]
- ./gradlew clean build -PdisableRyuk: [successful / failed — reason]
- ./build-harness-mysql-image.sh: [successful / failed — reason]

**Full suite results:**
- Status: [clean / pre-existing failures / new failures]
- If failures found:
  - Tests affected: [list of test names]
  - Pre-existing confirmed: [yes / no / not checked]
  - Developer action: [fixed in PR / separate ticket filed [ID] / acknowledged and skipped]
  - Collateral damage: [none / [description], impact: [description]]

## Retro Notes

[What worked well. What slowed things down. Any AVOD pattern that should be added to the domain knowledge. Any test setup that was harder than expected. Harness iteration patterns. Be honest — these notes improve the next ticket.]

---

## Evidence

- Scope: `[OUTPUT_DIR]/01-scope.md`
- Investigation: `[OUTPUT_DIR]/02-investigation.md`
- Roadmap: `[OUTPUT_DIR]/03-roadmap.md` (all steps: done)
- Code guide: `[OUTPUT_DIR]/04-code-guide.md`
- Implementation log: `[OUTPUT_DIR]/05-implementation-log.md`
- Pull request: `[OUTPUT_DIR]/06-pull-request.md`
- Commit: [hash]
- PR: [link or number]
```

Save to `[OUTPUT_DIR]/07-completion-report.md`.

Then ask:

```
Does this report look accurate? Yes / no?
```

- **Yes** → "✓ Ticket complete. All outputs in `[OUTPUT_DIR]/`."
- **No** → ask what's wrong, update, show again.

---

## Output Files

All saved to OUTPUT_DIR (chosen by the developer during setup; defaults to the repo root):

```
[OUTPUT_DIR]/
  01-scope.md               Stage 1 — confirmed scope statement
  02-investigation.md       Stage 2 — quoted code findings
  03-roadmap.md             Stage 3 — living plan (updated as steps complete)
  04-code-guide.md          Stage 4 — code guide + test plan
  05-implementation-log.md  Stage 5 — test results, checklist, commit hash
  06-pull-request.md        Stage 5 — PR description for developer/reviewers
  07-completion-report.md   Stage 6 — AI-attributed record
```

Create OUTPUT_DIR if it does not exist before writing any file.

---

## Status Words

Use these words consistently across all documents:

| Word | Means |
|------|-------|
| `done` | Verified — test passes or checklist passes, evidence in hand |
| `partial` | Some parts work — explicitly say which parts and which do not |
| `in progress` | Currently being worked on |
| `next` | The next step to start |
| `blocked` | Cannot proceed — name the blocker explicitly |
| `design only` | On paper, no implementation exists yet |

Never write `done` when the right word is `partial`. Never call something done because the code path exists — behavior must be verified by a passing test.

---

## AVOD Domain Reference

This reference is embedded here so the skill works without any external files.

### Session identity and AVOD eligibility

- `authUserId` may be null for anonymous users. Every code path must check for null before using it.
- AVOD-anonymous sessions have a specific `authUserId` format. Use `AccountMapDef.isAvodAnonymousSession(authUserId)` — do not write a new check.
- Three session types must be handled separately: anonymous (null authUserId), authenticated non-AVOD, authenticated AVOD-eligible.
- Non-AVOD behavior must be unchanged after any AVOD change.

### Redis

- TTL must be set explicitly on every Redis write. An entry without a TTL can grow unbounded.
- Redis key naming follows the convention in the module — check existing usages before writing a new key.
- After a session state change (login, logout, eligibility change), confirm that stale Redis entries are invalidated or ignored.

### Harness testing and building (director2-aws only)

**Harness tests:**
- Harness tests are XML files in `suite/<module>/test/`.
- Each test case has a `<name>`, `<input>` fields, and `<expected>` fields.
- Use `fakeAdvertContentDefinitionCreate` to make a content ID AVOD-eligible in a test.
- Lock `<now>` to a fixed timestamp when testing time-sensitive behavior.
- Use SQL fixtures (`.sql` files in the test directory) when no fake-create op exists.
- Run a single test: `./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<name>.xml`
- Run the full module suite: `./run-harness-sidecar.sh -p -m -t 10 <module>`

**Buildenv and image creation:**
- buildenv creates a Docker container with compilation environment
- Inside buildenv, compile and build the harness image:
  ```bash
  cd <module-directory>
  ./gradlew clean build -PdisableRyuk
  ./build-harness-mysql-image.sh
  ```
- Harness tests run OUTSIDE the container, on the host
- Developer can: (1) manually run buildenv steps, (2) choose automation, or (3) skip and use existing image
- Stale harness images may cause spurious test failures; rebuild if needed

**Collateral damage patterns:**
- When implementing a change, the full suite (`./run-harness-sidecar.sh -p -m -t 10 <module>`) may surface failures in unrelated tests
- These failures ("collateral damage") happen because:
  - The implementation affected shared state (Redis keys, database schema, mock data setup)
  - The test infrastructure is coupled and one module's change affects another
  - The harness image is stale and contains stale mock data
- To handle:
  1. Check if the failure exists on main branch (pre-existing)
  2. If new: decide to fix, file separate ticket, or acknowledge in code review
  3. Document the decision in the roadmap and completion report
  4. Code review must acknowledge any collateral damage before merge

### Spring Boot integration testing (other repos)

- Prefer `@SpringBootTest` integration tests for acceptance cases — they test the full stack.
- Use `@DataJpaTest` or `@WebMvcTest` for isolated unit tests where the full context is not needed.
- Use TestContainers for tests that need a real database or Redis instance.
- Use WireMock for tests that depend on external HTTP services.
- Transactional tests with `@Transactional` roll back automatically — use for tests that write to the DB.

### Content search (director2-aws)

- `contentSimilarSearch` and related Zoltar ops live in `suite/media2/src/`.
- Results are ranked by score. AVOD-eligible titles must be promoted before non-eligible titles for AVOD sessions.
- Do not modify the scoring logic — only the ordering of results returned to the caller.

### Code review — what to look for

Apply the full AVOD checklist from Stage 5 to every PR. Additionally:
- If the PR touches session handling, verify all three session types (anonymous, non-AVOD, AVOD).
- If the PR touches Redis, verify TTL and key naming.
- If the PR adds a new helper, verify it is not duplicating `AccountMapDef` or existing session utilities.
- If the PR modifies a Zoltar op, verify that non-AVOD behavior is tested and unchanged.

---

## Verification Checklist

After completing all six stages, confirm:

- [ ] Developer answered all five clarifying questions before investigation started
- [ ] Investigation quotes real code with file paths and line numbers — no prose summaries
- [ ] Roadmap was approved by the developer before any code was written
- [ ] Test was written and RED before implementation started
- [ ] Full suite was clean (or pre-existing failures confirmed) before Step 3 was marked done
- [ ] AVOD checklist ran against the diff — all items passed
- [ ] INT or staging confirmed expected behavior
- [ ] All seven output files exist in `[OUTPUT_DIR]/`
- [ ] Pull request document accurately describes the change for reviewers
- [ ] Completion report reflects what actually happened, not a template

---

## Red Flags

- Proceeding to Stage 2 before the scope gate passes
- Investigation says "probably" or "I think" about any code reference
- Roadmap step says "implement the feature" without naming a specific method or file
- Test is written after the implementation (the test passed immediately on first run)
- Suite failures dismissed without checking whether they are pre-existing
- AVOD checklist item skipped without the developer explicitly acknowledging it
- Completion report is a template — it does not reflect what actually happened on this specific ticket
- Developer chooses to skip buildenv but harness image is stale — test failures may be spurious
- Full suite (Step 3) has failures, but no decision made: fix, separate ticket, or acknowledged skip
- Collateral damage found but not acknowledged in code review (Step 4)
- PR merged without Step 3 marked `done` or without clear documentation of suite status
- Buildenv automated but fails silently; developer should fall back to manual or investigate error
