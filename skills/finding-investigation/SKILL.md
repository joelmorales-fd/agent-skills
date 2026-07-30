---
name: finding-investigation
description: Decide whether a finding is grounded, weakly grounded, ungrounded, or needs more evidence. Use when a generated finding looks plausible but not yet trustworthy, when a reviewer challenges a finding, when a claim may overreach what cited code proves, or when you need to decide whether to keep, narrow, drop, or continue investigating a finding.
---

# Finding Investigation

## Overview

Freeze the claim first. Investigate the claim second. Do not silently rewrite the finding while testing it.

This skill exists for one repeated loop: deciding whether a finding is grounded, weakly grounded, ungrounded, or still missing evidence.

## When to Use

- A generated finding looks plausible but not yet trustworthy
- A reviewer says a finding is wrong and you need to verify it
- A finding cites code, but the claim may overreach what the code proves
- A finding may be missing a caller, config path, test path, or data-flow step
- You need to decide whether to keep, weaken, reject, or continue investigating a finding

## When NOT to Use

- Broad review quality questions
- "What did the review miss?" investigations across many findings
- `benchmark-failure-triage` work
- Hook or runtime enforcement debugging

Use `code-review-gap-investigation`, `review-of-code-review`, `plugin-runtime-fix`, or `benchmark-failure-triage` for those.

## Required Inputs

- Exact finding text
- The diff, file, or code region the finding is about

Helpful inputs:

- File and line references already cited by the finding
- Review or benchmark artifact that produced the finding
- Any rebuttal explaining why the finding may be wrong

## Process

### Step 1: Freeze the finding

Record the finding exactly as written.

Minimum shape:

```md
Claim:
[exact finding text]
```

Do not paraphrase yet. The investigation is against this exact claim.

### Step 2: Extract the proof obligations

Ask what must be true for the finding to be correct.

Examples:

- If the finding says "this leaks resources", there must be a resource acquisition path and no cleanup path.
- If the finding says "this value can be null here", there must be a reachable path where null is possible at that exact use site.
- If the finding says "this benchmark regression is caused by X", X must explain the observed change, not just be a nearby difference.

Write down the minimum proof obligations before gathering more evidence.

### Step 3: Gather the smallest necessary evidence

Read the smallest set of artifacts that can prove or disprove the claim:

- Cited file and line
- Direct caller
- Direct callee
- One related config or test file if needed

Do not fan out into a full repo investigation unless the claim cannot be resolved locally.

### Step 4: Separate fact from inference

For every important statement, classify it as:

- Direct fact from code
- Inference from code
- Assumption not yet proven

Do not present inferences as if they were direct evidence.

### Step 5: Check reachability

Many weak findings are technically plausible but not reachable.

Check:

- Can the code path actually execute?
- Can the relevant value actually take the claimed state?
- Is there a caller that supplies the bad input?
- Is the dangerous branch dead, guarded, or impossible under current constraints?

If reachability is missing, the finding usually becomes `Weakly grounded` or `Needs more evidence`.

### Step 6: Check scope match

Make sure the evidence answers the same claim you started with.

Common failure:

- Original claim: null dereference at line X
- Discovered issue: stale cache behavior in the same function
- Wrong conclusion: "finding is grounded"

That is a scope mismatch. The discovered issue may be real, but it does not validate the original finding.

### Step 7: Classify the finding

Use one of these verdicts:

- `Grounded`
- `Weakly grounded`
- `Ungrounded`
- `Needs more evidence`

Use `Grounded` when direct code evidence supports the claim and no major missing step remains.

Use `Weakly grounded` when the concern is plausible but at least one important step still depends on inference.

Use `Ungrounded` when the cited code does not support the claim, or the traced path contradicts it.

Use `Needs more evidence` when the claim might be true, but a critical path, file, config, or runtime fact has not been checked yet.

### Step 8: End with one next action

Never stop at the verdict alone.

Allowed next actions:

- Keep the finding as written
- Rewrite the finding to a narrower claim
- Drop the finding
- Inspect one caller
- Inspect one config file
- Run one targeted test or probe

Choose the smallest next move that reduces uncertainty fastest.

## Output Format

Use this output every time:

```md
# Finding Investigation

## Claim
[exact finding text]

## Verdict
Grounded | Weakly grounded | Ungrounded | Needs more evidence

## Evidence
- [file:line] [what this proves]
- [file:line] [what this proves]

## Missing Evidence
- [what is still not proven]

## Notes
- Facts:
  - [fact]
- Inferences:
  - [inference]

## Next Action
[one concrete next step]
```

## Red Flags

The workflow is drifting if:

- The finding is paraphrased before being tested
- Evidence is gathered without defining what must be proven
- Nearby issues are used to justify the original claim
- The conclusion says "probably" without saying what is missing
- The output gives multiple next actions instead of one smallest next move

## Common Rationalizations

- "The code looks suspicious, so the finding is probably right"
- "A nearby issue proves the original claim"
- "We do not need to trace reachability for a plausible bug"
- "Missing one proof step is fine if the concern feels directionally correct"

## Verification

- Confirm the verdict uses one canonical label: `Grounded`, `Weakly grounded`, `Ungrounded`, or `Needs more evidence`
- Confirm every major claim in the output is backed by direct evidence or explicitly marked as inference
- Confirm the evidence still answers the frozen original claim, not a nearby issue
- Confirm the output ends with exactly one next action

## Boundaries

This skill standardizes reasoning and output. It does not own:

- Benchmark orchestration
- Review completeness judgments across many findings
- Hook or runtime enforcement

Keep those in separate workflows.
