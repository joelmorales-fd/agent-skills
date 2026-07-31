---
name: mutation-test-check
description: Decide whether mutation testing is worth running, narrow it to the smallest useful scope, and turn surviving mutants into concrete test or review follow-up. Use when normal tests pass but you still need evidence that those tests would catch meaningful logic mistakes, when you want to know whether tests are actually strong, or when a review says code is covered by tests and you want proof.
---

# Mutation Test Check

## Overview

Mutation testing is a verification escalation, not a default step.

Use it to answer one repeated question:

"Do these passing tests actually protect the logic that matters?"

This skill exists to decide when mutation testing is worth the cost, keep the scope small, and separate useful survivors from noise.

## When to Use

- A behavior-changing code path already has passing tests, but confidence is still weak
- The changed code has meaningful logic: branching, filtering, validation, calculations, policy checks, state transitions
- A review says "covered by tests" and you want proof
- A finding claims the tests are weak and you need evidence
- You are comparing two verification strategies and want a stronger signal than coverage alone

## When NOT to Use

- Docs-only, config-only, or mechanical refactor changes
- Broad integration failures where the basic test environment is still unstable
- Whole-repo sweeps "just to see what happens"
- UI copy, generated code, or glue code with little business logic
- A module whose baseline tests are already failing
- The repo has no mutation-testing tool configured and the user did not ask to introduce one

Use `test-driven-development`, `code-review-and-quality`, `finding-investigation`, or `review-of-code-review` first if the real problem is missing tests, weak review quality, or an unverified finding. Come back to this skill when mutation testing is the right next proof step.

## Mutation Gate

Run mutation testing only when all of these are true:

- The change affects behavior, not just formatting or comments
- The ordinary tests for that area are already green
- The target logic is narrow enough to isolate to one module, package, file group, or command
- The cost of being wrong is high enough to justify slower verification
- You have a realistic way to interpret survivors instead of blindly counting them
- A mutation-testing tool already exists for this repo, or the user explicitly wants to add one

If any gate fails, skip mutation testing and say why.

## Process

### Step 1: Freeze the question

State the exact reason you are considering mutation testing.

Examples:

- "I need to know whether these new validation tests would fail if the branch logic changed."
- "I need evidence for whether this review's 'well tested' claim is real."
- "I need to know whether this benchmark fix is protected by assertions or only exercised incidentally."

Do not start from "run mutation testing because it exists."

### Step 2: Pick the smallest mutation scope

Default to the narrowest useful scope:

- One changed class or module
- One package with related business rules
- One command or service boundary

Do not start with a whole repo or whole application run unless the tool only supports that and the codebase is small enough that the result is still interpretable.

### Step 3: Confirm the baseline is trustworthy

Before running mutation testing:

- Run the ordinary tests for the chosen scope
- Confirm they pass
- Confirm the test failures, if any, are not infrastructure noise

If the baseline is not green, mutation output is not trustworthy yet.

### Step 4: Run the smallest useful mutation pass

Use the project's existing mutation tool if it already has one. Do not introduce a new tool unless the user asked for it or the repo clearly wants one.

Prefer:

- The tool already used by the repo
- The smallest target selection the tool supports
- The smallest test set that still exercises the target logic

Capture:

- Exact scope mutated
- Test command used
- Mutation summary
- List of survivors for later triage

### Step 5: Triage survivors, do not worship the score

Every survivor must be classified before you decide what it means.

Allowed survivor classes:

- `Real gap`
- `Equivalent or low-value mutant`
- `Environment or tooling noise`
- `Needs manual inspection`

Use `Real gap` when the survivor shows the tests did not notice a meaningful logic change.

Use `Equivalent or low-value mutant` when the mutation does not change behavior in any meaningful way, or only changes dead or redundant logic.

Use `Environment or tooling noise` when the result is dominated by timeouts, flaky startup, unsupported language features, or broken instrumentation.

Use `Needs manual inspection` when the mutant may matter but the result is not obvious yet.

### Step 6: Convert real gaps into exact follow-up

For every `Real gap`, define the smallest correction:

- Add one missing assertion
- Add one missing branch test
- Add one missing property or invariant check
- Split one broad integration test into one smaller logic test

Do not answer a survivor with "add more tests" as a vague slogan.

### Step 7: Decide whether mutation testing helped

Use one outcome:

- `Useful signal`
- `Useful with noise`
- `Not worth it for this scope`

Use `Useful signal` when the run exposed clear test weaknesses or meaningfully increased confidence.

Use `Useful with noise` when the run helped, but the environment, tooling, or equivalent mutants created cleanup cost.

Use `Not worth it for this scope` when the run was too noisy, too broad, or too expensive relative to what it taught you.

### Step 8: End with one next action

Choose one next move only:

- Add one targeted test
- Narrow the mutation scope and rerun
- Mark the survivors as equivalent and stop
- Skip mutation for this area and rely on ordinary tests
- Stop and report that no mutation-testing tool is configured for this repo
- Escalate to manual review of one suspicious survivor

## Output Format

Use this output every time:

```md
# Mutation Test Check

## Question
[why mutation testing is being considered]

## Scope
[exact file/module/package/test scope]

## Baseline
Pass | Fail | Unstable

## Tooling
Configured | Missing | Unstable

## Outcome
Useful signal | Useful with noise | Not worth it for this scope

## Survivors
- [mutant or category] -> Real gap | Equivalent or low-value mutant | Environment or tooling noise | Needs manual inspection

## Follow-up
- [smallest concrete correction or decision]

## Next Action
[one concrete next step]
```

## Common Rationalizations

- "Coverage is high, so mutation testing is unnecessary"
- "The score went up, so the tests must now be good"
- "We should run this across the whole repo for completeness"
- "A survivor always means a missing test"
- "The tool output is noisy, so mutation testing is useless everywhere"

## Red Flags

The workflow is drifting if:

- Mutation testing is run before ordinary tests are green
- The chosen scope is much larger than the changed logic
- The result is summarized as one score with no survivor triage
- Equivalent mutants are counted as if they were real failures
- Tooling noise is treated as evidence about test quality
- The output ends with multiple vague follow-ups instead of one next move

## Verification

- Confirm the mutation gate was evaluated explicitly before running anything
- Confirm the chosen scope is the smallest useful one
- Confirm the baseline test status is recorded as `Pass`, `Fail`, or `Unstable`
- Confirm the tooling status is recorded as `Configured`, `Missing`, or `Unstable`
- Confirm every survivor listed has one classification
- Confirm the output ends with exactly one next action
