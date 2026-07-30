---
name: evidence-packet-prep
description: Build a compact evidence packet for a later investigation or review-quality workflow. Use when raw transcript output, logs, reviews, diffs, or benchmark artifacts are too noisy to judge directly and you need the smallest trustworthy packet for `finding-investigation`, `code-review-gap-investigation`, `review-of-code-review`, or `benchmark-failure-triage`.
---

# Evidence Packet Prep

## Overview

This skill exists for one repeated loop: preparing the smallest trustworthy packet another workflow can judge quickly.

Do not decide the final issue here. Build the packet that makes the later decision easier and safer.

## When to Use

- A later step needs focused evidence instead of raw transcript noise
- A review, log, or benchmark artifact is too large to judge directly
- You want to hand work from one model or session to another
- You need to preserve the real evidence before summarization or rewriting
- You are preparing inputs for `finding-investigation`, `code-review-gap-investigation`, `review-of-code-review`, or `benchmark-failure-triage`

## When NOT to Use

- Delivering the final verdict on whether a finding or review is right
- Running the benchmark, probe, or harness itself
- Storing long-term history or runtime state
- Collecting everything "just in case"

Use the downstream workflow once the packet is ready.

## Required Input

- One exact question the packet must answer

Examples:

- Is finding 3 grounded?
- Did this code review miss a regression risk?
- Is this benchmark change real?

Possible source material:

- Diffs
- Files
- Review output
- Benchmark output
- Logs
- Test results
- Prompt artifacts
- Previous investigations

## Process

### Step 1: Freeze the question

Write the exact question first.

Bad:

- "Collect useful evidence"

Good:

- "Collect evidence needed to judge whether finding 3 is grounded"

If the question is broad, narrow it before gathering artifacts.

### Step 2: Identify the required evidence types

Ask what artifact types are actually needed.

Examples:

- Finding grounding: finding text, cited code, direct caller or callee if needed
- Code review gap: review artifact, diff, hotspot files
- Benchmark failure triage: baseline, current result, scenario metadata

Do not collect evidence types that are not required for the frozen question.

### Step 3: Gather minimal artifacts

Prefer:

- Exact file excerpts
- Exact review sections
- Exact commands and outputs
- Exact benchmark slices

Avoid:

- Entire transcripts when one block is enough
- Whole logs when one failure segment is enough
- Unrelated files

### Step 4: Separate fact from interpretation

For each item, classify it as:

- `Raw artifact`
- `Extracted fact`
- `Interpretation`

Do not let interpretation masquerade as evidence.

### Step 5: Remove noise

Cut anything that does not help answer the frozen question.

Common noise:

- Unrelated findings
- Old failed attempts
- Broad design notes
- Duplicate evidence
- Narrative commentary with no proof value

### Step 6: Check packet sufficiency

Ask:

- Could someone new answer the question from this packet?
- Is one critical artifact still missing?
- Is anything included only because it "might be useful"?

If "might be useful" is the only reason, cut it.

### Step 7: Produce the packet

The packet must end with:

- The exact question
- The included evidence and why each item is present
- The facts extracted from that evidence
- Explicit missing evidence
- Which downstream workflow the packet is ready for

## Output Format

Use this output every time:

```md
# Evidence Packet

## Question
[exact question]

## Included Evidence
- [artifact] - [why it is included]
- [artifact] - [why it is included]

## Facts Extracted
- [fact]
- [fact]

## Missing Evidence
- [missing item or None]

## Packet Ready For
finding-investigation | code-review-gap-investigation | review-of-code-review | benchmark-failure-triage
```

## Red Flags

The workflow is drifting if:

- The packet is built before the question is frozen
- The packet contains large raw dumps with no selection logic
- Interpretation is mixed in without being marked
- Multiple downstream workflows are targeted at once
- The packet grows because it feels safer to include everything

## Common Rationalizations

- "Include everything so nothing gets missed"
- "The packet can target several downstream workflows at once"
- "Interpretation is fine as long as it sounds plausible"
- "A large raw dump is safer than a selected packet"

## Verification

- Confirm the packet answers one frozen question only
- Confirm every included artifact has a reason for being present
- Confirm facts and interpretation are not mixed together
- Confirm the packet names exactly one downstream workflow target

## Boundaries

This skill improves later reasoning quality. It does not own:

- The final verdict on the issue
- Benchmark execution or probing
- Runtime storage or history persistence

Keep those in other workflows.
