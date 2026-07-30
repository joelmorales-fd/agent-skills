---
name: code-review-gap-investigation
description: Investigate whether a code review missed an important issue, used the wrong frame, or stopped too early. Use when a later bug, benchmark result, or follow-up investigation suggests the original code review may have missed something meaningful and you need a disciplined way to decide whether a real review gap exists.
---

# Code Review Gap Investigation

## Overview

This skill exists for one repeated question:

"What did the review miss?"

Do not use it to judge overall review quality in the abstract. Use it to investigate a suspected missing issue against a specific review and a fixed reviewed scope.

## When to Use

- A real issue was found after review
- A benchmark failure suggests the review missed a relevant risk
- A human says the review felt incomplete
- A later investigation finds a more important issue than the original review emphasized
- You need to know whether the original review should reasonably have caught a later issue

## When NOT to Use

- Validating whether one finding is grounded
- Judging overall review quality without a specific suspected miss
- Triage of benchmark validity rather than review completeness
- Generic second-pass code review with no concrete missing-issue hypothesis

Use `finding-investigation`, `review-of-code-review`, or `benchmark-failure-triage` for those.

## Required Inputs

- The original review text
- The reviewed diff or reviewed artifact set
- The later-discovered issue or candidate missing issue
- Any evidence the review actually cited

Helpful inputs:

- Benchmark output that exposed the gap
- Prior review version if multiple passes exist
- Known hotspot notes for the touched subsystem

## Process

### Step 1: State the suspected gap precisely

Write the missing issue in one sentence.

Bad:

- "The review was weak."
- "It missed stuff."

Good:

- "The review missed that the hook path regression broke live declaration enforcement."
- "The review missed the stale command/skill drift between `commands/avod.toml` and `skills/avod-ticket/SKILL.md`."

If you cannot state the missing issue clearly, narrow it first.

### Step 2: Check whether the issue was visible in the reviewed scope

Ask:

- Was the relevant file in the reviewed diff?
- Was the relevant behavior implied by the reviewed change?
- Was nearby evidence present even if not directly changed?

Use one visibility result:

- `Directly visible`
- `Indirectly visible`
- `Not meaningfully visible`

Not every later issue counts as a review miss.

### Step 3: Compare the review's attention map to the real risk map

Build two short lists.

Review attention map:

- What the review actually discussed
- Which files or behaviors it emphasized
- Which risks it seemed to optimize for

Real risk map:

- What actually mattered in the later issue or failure
- Which files or behaviors drove the outcome
- Which risk class the issue belongs to

This is usually where the gap becomes obvious.

### Step 4: Classify the miss

Choose exactly one primary classification:

- `Hotspot miss`
- `Evidence miss`
- `Reasoning miss`
- `Scope miss`
- `Expectation miss`

Use `Hotspot miss` when the review failed to inspect the subsystem or file area most likely to contain the real risk.

Use `Evidence miss` when the needed evidence was in scope, but the review did not extract or use it.

Use `Reasoning miss` when the review saw the evidence but reached the wrong conclusion or stopped too soon.

Use `Scope miss` when the review was framed too narrowly and excluded a risk it should have included.

Use `Expectation miss` when the review used the wrong standard for what mattered.

### Step 5: Decide whether the miss was reasonably detectable

Use one of:

- `Clearly detectable`
- `Detectable with normal diligence`
- `Detectable only with specialized context`
- `Not reasonably detectable`

Use `Clearly detectable` when the missing issue was obvious from the reviewed scope and evidence.

Use `Detectable with normal diligence` when it was visible but required a careful pass.

Use `Detectable only with specialized context` when the review could catch it only if it knew domain-specific risks.

Use `Not reasonably detectable` when the later issue depended on evidence outside the reviewed scope.

If the issue was not reasonably detectable, the fix is usually context or expectation improvement, not "review harder."

### Step 6: Decide whether a real review gap exists

Use one verdict:

- `Real gap`
- `Partial gap`
- `No meaningful gap`
- `Needs more evidence`

Use `Real gap` when the missing issue matters, was reasonably detectable, and the review did not cover it in a useful way.

Use `Partial gap` when the review touched the area but did not articulate the real issue clearly enough.

Use `No meaningful gap` when the issue was not reasonably detectable from the reviewed scope, or the review effectively covered it already.

Use `Needs more evidence` when the later issue is still too fuzzy to judge against the original review.

### Step 7: Identify the smallest process improvement

Do not end with "the review should be better."

Choose one smallest improvement:

- Add one checklist item
- Add one hotspot reminder
- Change one prompt instruction
- Require one evidence citation rule
- Add one benchmark comparison step
- Split one overloaded review task into two

If the proposed fix is a broad redesign, reduce the problem further.

### Step 8: End with one next action

Every output must end with one concrete next move.

Examples:

- Add one new checklist item to the workflow
- Re-run the review with one hotspot reminder
- Promote one later issue into the review benchmark set
- Drop the complaint because the issue was not reasonably detectable

Choose the smallest next move that best reduces future miss risk.

## Output Format

Use this output every time:

```md
# Code Review Gap Investigation

## Reviewed Scope
[what artifact, diff, or review was evaluated]

## Suspected Missing Issue
[one-sentence statement]

## Verdict
Real gap | Partial gap | No meaningful gap | Needs more evidence

## Visibility
Directly visible | Indirectly visible | Not meaningfully visible

## Gap Classification
Hotspot miss | Evidence miss | Reasoning miss | Scope miss | Expectation miss

## Detectability
Clearly detectable | Detectable with normal diligence | Detectable only with specialized context | Not reasonably detectable

## What The Review Covered
- [point]

## What The Review Missed
- [point]

## Why It Was Missed
[short explanation]

## Smallest Improvement
[one concrete change]

## Next Action
[one concrete next move]
```

## Red Flags

The workflow is drifting if:

- It turns into a generic second review
- It uses hindsight unfairly
- It treats every later bug as a review failure
- It cannot state the missing issue in one sentence
- It ends with a vague process complaint instead of one smallest improvement

## Common Rationalizations

- "A later bug automatically means the review failed"
- "The review mentioned the file, so it covered the real risk"
- "Hindsight is fine because the issue now looks obvious"
- "The improvement should be a broader review process overhaul"

## Verification

- Confirm the missing issue is stated in one sentence
- Confirm the reviewed scope is fixed and the judgment is based only on evidence that was reasonably available
- Confirm the output uses one primary classification and one detectability level
- Confirm the output ends with one smallest improvement and one next action

## Boundaries

This skill standardizes review-gap diagnosis. It does not own:

- Validation of a single finding
- Overall review quality scoring
- Benchmark execution or harness orchestration
- Hook or runtime enforcement

Keep those in separate workflows.
