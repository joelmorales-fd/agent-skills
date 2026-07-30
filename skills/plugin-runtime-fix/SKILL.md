---
name: plugin-runtime-fix
description: Fix when a plugin, hook, command, matcher, or approval flow is supposed to work but does not behave correctly in the live runtime. Use when you need to confirm the mismatch, determine whether the problem is in repo files, installed cache, session state, or runtime support, apply the smallest fix, and verify the result with one live test.
---

# Plugin Runtime Fix

## Overview

This skill exists for one repeated loop: make the live plugin behavior work, then prove it works.

The investigation is only there to find the smallest real fix. Do not stop at diagnosis if a safe concrete fix is available.

## When to Use

- A hook should fire but does not
- A matcher, command, or approval flow behaves differently than expected
- A plugin change landed in the repo but the live runtime still behaves like the old version
- Claude, Codex, or another runtime surface appears to use the wrong file copy or stale state
- You need to know whether a runtime fix is real, not just edited in one place

## When NOT to Use

- Writing a brand new plugin or hook from scratch
- Broad infrastructure redesign
- Application code debugging unrelated to plugin behavior
- Declaring success without one live verification step

Use this skill when the goal is fix-and-verify, not just explanation.

## Required Inputs

- The expected behavior
- The observed live behavior

Helpful inputs:

- Repo path for the plugin or hook files
- Installed plugin cache path if known
- Live config path if known
- Session or thread identifier if relevant
- One small test that can prove the behavior

## Process

### Step 1: Freeze the mismatch

State the expectation and the observed behavior in one or two lines.

Minimum shape:

```md
Expected:
[what should happen]

Observed:
[what actually happened]
```

If the mismatch is vague, narrow it before changing anything.

### Step 2: Check the three likely layers

Inspect:

- Repo files
- Installed plugin cache files
- Live runtime config or session state

Look for the smallest mismatch that explains the behavior:

- repo copy is wrong
- installed cache is stale
- session state is stale
- runtime does not support the expected behavior

Do not assume the repo copy is the live truth.

### Step 3: Name the root cause

Use one root-cause label:

- `Repo mismatch`
- `Cache mismatch`
- `Session stale state`
- `Runtime capability gap`
- `Unclear root cause`

If more than one seems true, choose the first layer that actually explains the live failure.

### Step 4: Apply the smallest fix

Choose the least change that can make the runtime behavior correct.

Examples:

- Change one repo file
- Sync installed plugin cache from repo
- Reinstall or reload the plugin
- Replace stale declaration or temp state
- Stop depending on an unsupported runtime behavior

Avoid broad cleanup if one targeted fix is enough.

### Step 5: Prove the fix with one live test

Run the smallest safe test that answers the frozen question.

Examples:

- Trigger one hook with one controlled file write
- Run one command with one known input
- Check one approval-gated write path
- Verify one matcher against one exact tool call

The test should prove the fix, not reopen the whole investigation.

### Step 6: Classify the result

Use one result:

- `Fixed and verified`
- `Partially fixed`
- `Blocked by runtime capability`
- `Not yet verified`

Use `Fixed and verified` when the live test shows the behavior now matches expectation.

Use `Partially fixed` when one problem is resolved but the frozen mismatch is not fully gone.

Use `Blocked by runtime capability` when the runtime itself does not support the expected behavior.

Use `Not yet verified` when you still cannot prove that the applied fix actually resolves the frozen mismatch.

### Step 7: End with the next move

If fixed, the next move is usually to keep the fix and stop.

If not fixed, end with one smallest next move:

- change one additional file
- refresh one cache or session layer
- downgrade the expectation to the supported runtime behavior
- run one sharper proof test

Do not end with a vague recommendation.

## Output Format

Use this output every time:

```md
# Plugin Runtime Fix

## Expected Behavior
[what should happen]

## Observed Behavior
[what actually happened]

## Root Cause
Repo mismatch | Cache mismatch | Session stale state | Runtime capability gap | Unclear root cause

## Fix Applied
- [change]

## Live Verification
- [test run]
- [result]

## Result
Fixed and verified | Partially fixed | Blocked by runtime capability | Not yet verified

## Next Move
[one concrete next move, or "None"]
```

## Red Flags

The workflow is drifting if:

- It stops after diagnosis even though a safe fix is available
- It changes several layers at once without proving which one mattered
- It never runs a live verification step
- It treats repo edits as proof of success
- It ends with a broad redesign instead of one next move

## Common Rationalizations

- "The repo file is correct, so the runtime must be correct too"
- "A cache or session problem is too annoying to verify, so just patch more files"
- "One local edit counts as a fix even without a live test"
- "Several possible causes can be fixed at once and sorted out later"

## Verification

- Confirm the expected and observed behavior are both stated explicitly
- Confirm one root cause label is chosen before or alongside the fix
- Confirm the fix applied is the smallest change that could resolve the mismatch
- Confirm one live test was run and the result section matches that test outcome

## Boundaries

This skill fixes and verifies plugin-runtime behavior. It does not own:

- Hook execution infrastructure
- Trust or sandbox policy
- Plugin loading semantics
- Runtime tool compatibility rules

It can work around or report those boundaries, but it should not pretend to control them.
