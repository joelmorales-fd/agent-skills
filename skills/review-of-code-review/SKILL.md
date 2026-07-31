---
name: review-of-code-review
description: Judge the quality of a code review artifact rather than the code under review. Use when comparing code review outputs, deciding whether a code review is trustworthy enough to act on, evaluating whether a prompt or workflow change improved code review quality, or checking whether a code review is grounded, complete enough, proportionate, and useful. If a review claims the code is well tested and you need proof, continue with `mutation-test-check`.
---

# Review of Code Review

## Overview

This skill exists for one repeated question:

"How good was this code review?"

Judge the code review as a decision-making artifact, not just a bag of individually true or false statements.

## When to Use

- Compare two review outputs for the same change
- Decide whether a review is trustworthy enough to act on
- Evaluate whether a prompt or workflow change improved code review quality
- Decide whether a benchmark failure reflects poor review quality
- Check whether a review is grounded, complete enough, proportionate, and useful
- Check whether a review's "well tested" claim needs stronger evidence than a passing suite

## When NOT to Use

- Validate one finding in isolation
- Investigate one specific missing issue
- Triage benchmark validity rather than review quality
- Re-review the code directly without using the review artifact as the object of judgment

Use `finding-investigation`, `code-review-gap-investigation`, or `benchmark-failure-triage` for those.

## Required Inputs

- The review text
- The reviewed diff or change scope

Helpful inputs:

- Benchmark or test outcomes
- A later bug or later finding set
- Known subsystem hotspot notes
- A comparison review from another run

## Evaluation Dimensions

Every review-of-code-review uses these six dimensions:

1. `Grounding`
2. `Risk focus`
3. `Completeness`
4. `Proportionality`
5. `Actionability`
6. `Signal-to-noise ratio`

Use one score per dimension:

- `Strong`
- `Acceptable`
- `Weak`
- `Failing`

## Process

### Step 1: Read the review as a decision artifact

Do not start by fact-checking every sentence.

Ask first:

- If I were the engineer receiving this review, would I trust it to decide my next step?

That frames the review correctly.

### Step 2: Score grounding

Ask:

- Does the review cite real files or behaviors?
- Are major claims directly supported?
- Are conclusions inference-heavy without saying so?

Score `Grounding` as `Strong`, `Acceptable`, `Weak`, or `Failing`.

### Step 3: Score risk focus

Ask:

- Did the review prioritize the risks that actually matter?
- Did it focus on correctness and regression risk where appropriate?
- Did it spend too much attention on low-value concerns?
- Did it follow behavior, not just syntax?

Score `Risk focus`.

### Step 4: Score completeness

Ask:

- Did the review cover the main risk surface?
- Did it miss important issues?
- Did it ignore expected hotspots?
- Was the scope interpreted too narrowly?

Score `Completeness`.

### Step 5: Score proportionality

Ask:

- Are weak concerns presented as major problems?
- Are major risks buried next to style notes?
- Is the balance between confidence and uncertainty honest?

Score `Proportionality`.

### Step 6: Score actionability

Ask:

- Are findings specific enough to verify or fix?
- Is the next step clear?
- Do the findings separate distinct concerns cleanly?

Score `Actionability`.

### Step 7: Score signal-to-noise ratio

Ask:

- Does the review include filler or inflated concerns?
- Does noise make the important findings harder to see?
- Would a shorter review have been better?

Score `Signal-to-noise ratio`.

### Step 8: Identify the dominant failure mode

If the review is weak or mixed, choose one primary failure mode:

- `Ungrounded review`
- `Missed-risk review`
- `Inflated review`
- `Noisy review`
- `Under-actionable review`
- `Mixed review`

Use one dominant failure mode only. The point is to name the main weakness, not to list every flaw.

### Step 9: Decide whether it is safe to act on

Use one safety verdict:

- `Safe to act on`
- `Safe with caution`
- `Needs targeted second pass`
- `Not safe to rely on`

Use `Safe to act on` when the review is strong enough that a human can proceed confidently.

Use `Safe with caution` when the review is useful but has one or two weak spots that must be kept in mind.

Use `Needs targeted second pass` when the review is mostly useful but key areas need re-evaluation.

Use `Not safe to rely on` when the review is too ungrounded, incomplete, noisy, or misprioritized to trust.

### Step 10: Name the smallest improvement

Do not end with "make the review better."

Choose one smallest improvement:

- Require file evidence for every major claim
- Add hotspot checklist for runtime-integration changes
- Separate missing-finding analysis from generic review output
- Drop low-confidence findings unless supported by code evidence
- Rebalance severity so high-risk issues are not buried

### Step 11: End with one next action

Every output must end with one concrete next move.

Examples:

- Run a targeted second pass on one risk area
- Drop the review from benchmark acceptance
- Promote one stronger review template
- Re-run with one stricter grounding rule

Choose the smallest next move that improves trust fastest.

## Verdict Rules

Use one overall verdict:

- `Strong review`
- `Usable review`
- `Mixed review`
- `Weak review`

Use `Strong review` when the review is well-grounded, focused on meaningful risks, complete enough for the scope, and easy to act on.

Use `Usable review` when the review is helpful and mostly trustworthy, but still has some weakness in completeness, proportionality, or noise.

Use `Mixed review` when the review contains valuable findings but also misses important things or inflates weak ones.

Use `Weak review` when the review is too ungrounded, incomplete, noisy, or misprioritized to trust.

## Output Format

Use this output every time:

```md
# Review of Code Review

## Scope
[what review and what change were evaluated]

## Verdict
Strong review | Usable review | Mixed review | Weak review

## Safe To Act On
Safe to act on | Safe with caution | Needs targeted second pass | Not safe to rely on

## Dimension Scores
- Grounding: Strong | Acceptable | Weak | Failing
- Risk focus: Strong | Acceptable | Weak | Failing
- Completeness: Strong | Acceptable | Weak | Failing
- Proportionality: Strong | Acceptable | Weak | Failing
- Actionability: Strong | Acceptable | Weak | Failing
- Signal-to-noise ratio: Strong | Acceptable | Weak | Failing

## Best Parts
- [point]

## Main Problems
- [point]

## Dominant Failure Mode
Ungrounded review | Missed-risk review | Inflated review | Noisy review | Under-actionable review | Mixed review

## Missing Important Findings
- [finding or "None"]

## Inflated Or Weak Findings
- [finding or "None"]

## Smallest Improvement
[one concrete change]

## Next Action
[one concrete next move]
```

## Red Flags

The workflow is drifting if:

- It mistakes correctness for usefulness
- It overweights formatting polish
- It treats verbosity as thoroughness
- It scores the review without comparing it to the actual reviewed scope
- It lists many problems but cannot name one dominant failure mode

## Common Rationalizations

- "The review is long, so it must be thorough"
- "Several true findings are enough even if the review missed the main risk"
- "Good formatting makes the review trustworthy"
- "A review is usable without a clear next action"

## Verification

- Confirm all six dimensions are scored
- Confirm the verdict matches the dimension scores and the described failure mode
- Confirm the judgment is based on the review artifact plus the actual reviewed scope
- Confirm the output ends with one smallest improvement and one next action

## Boundaries

This skill judges the review artifact itself. It does not own:

- Validation of a single finding
- Investigation of one specific missing issue
- Benchmark execution or harness orchestration
- Hook or runtime enforcement

Keep those in separate workflows.
