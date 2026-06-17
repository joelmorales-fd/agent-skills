---
name: avod-ticket-spec
description: Specification for AVOD ticket skill — six-stage workflow with flexible harness iteration, optional buildenv automation, and collateral damage detection
---

# AVOD Ticket Skill Specification

## Objective

Enhance the AVOD ticket skill to handle **harness iteration complexity** in director2-aws by:
1. Allowing developers to choose manual or automated harness builds
2. Detecting and managing suite failures from collateral damage
3. Requiring pre-existing failure confirmation before proceeding
4. Enforcing code review on all paths to `done`

## Core Problem

When running the full harness suite (`./run-harness-sidecar.sh -p -m -t 10 <module>`), unrelated tests may fail due to side effects from code changes. This creates an undocumented iteration loop:
- Developer changes code for Feature X
- Harness suite fails on Test Y (unrelated)
- Developer must either: (a) fix Test Y, (b) document it as pre-existing, or (c) abandon the change

The current skill doesn't guide this decision or document the outcome.

## Proposed Changes

### Change 1: Add buildenv and image creation as optional sub-steps

**Location:** Stage 5, Step 2 (Implement the change)

**Current text:**
```
**director2-aws:** After each iteration, recompile inside the build container:
./gradlew clean build
Then run the specific test from the host:
./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<test-name>.xml
```

**Replace with:**
```
**director2-aws:** After each iteration, you have three options:

**Option 1: Manual buildenv (developer controls)**
1. Run buildenv to start Docker container:
   buildenv
2. Inside the container, compile and create the harness image:
   cd <module-directory>
   ./gradlew clean build -PdisableRyuk
   ./build-harness-mysql-image.sh
3. Exit the container
4. From the host, run the specific test:
   ./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<test-name>.xml

**Option 2: Automated buildenv (skill manages)**
Ask: "Should I automate the buildenv setup and image creation? (yes / no)"
- If yes: Skill runs buildenv internally, executes compile and image build, then runs the test
- If no: Fall back to Option 1

**Option 3: Skip buildenv (fast iteration)**
If you're iterating quickly on the implementation without harness artifacts, skip buildenv:
./run-harness-sidecar.sh -p -t 1 -j 2048 /<module>/test/<test-name>.xml
(Note: This may fail if the harness image is stale. Rebuild if needed.)

When the test passes (GREEN), update Step 2 in the roadmap to `done`.
```

---

### Change 2: Add collateral damage detection in Step 3

**Location:** Stage 5, Step 3 (Run the full suite)

**Current text:**
```
- If clean → update Step 3 to `done`
- If failures → show the failures. Ask: "Are these pre-existing failures or new ones caused by your change? (pre-existing / new)"
  - `pre-existing` → confirm by checking git blame or running on main branch, then proceed
  - `new` → must be fixed before continuing. Stay on Step 3 until clean.
```

**Replace with:**
```
**director2-aws:**
```bash
./run-harness-sidecar.sh -p -m -t 10 <module>
```

### Full suite results handling

If **clean** (no failures):
→ update Step 3 to `done`, proceed to Step 4

If **failures found**:
Show the failures with test names and error details.

Ask: **"Which best describes these failures?"**

**Option A: Pre-existing (not caused by my change)**
1. Confirm by running the test on main/master branch WITHOUT your changes:
   ```
   git stash
   ./run-harness-sidecar.sh -p -m -t 10 <module>
   git stash pop
   ```
2. If the test fails on main too → pre-existing ✓
3. Document in roadmap: "Step 3 — suite has [N] pre-existing failures in [test names]"
4. Proceed to Step 4

**Option B: New (caused by my change)**
You have three choices:

1. **Fix in this PR** (recommended)
   - Investigate the failing test
   - Fix the root cause in your implementation
   - Re-run the full suite
   - Loop back to Step 3 until clean

2. **File separate ticket**
   - Document which tests failed and why
   - Note that this PR causes collateral damage
   - Create a follow-up ticket to fix the underlying issue
   - This PR will be marked `blocked` until decision is made

3. **Skip for now** (rare)
   - Mark Step 3 as `partial` with details: "Suite fails on [tests]; developer chose not to fix"
   - Mark overall ticket `needs-decision` — this path requires explicit developer acknowledgment
   - Cannot proceed to merge without explicit override

**Final gate for Step 3:**
Step 3 is `done` ONLY when:
- [ ] Suite is fully clean, OR
- [ ] All failures are confirmed pre-existing AND documented in roadmap, OR
- [ ] Developer explicitly chose Option B.2 (separate ticket) or B.3 (skip), with acknowledgment
```

---

### Change 3: Add code review as a requirement before final `done`

**Location:** Stage 5, Step 4 → renamed to "Final Code Review"

**Current text (unchanged conceptually, but strengthened):**
```
### Step 4: Code review — AVOD checklist
```

**Add at the end of Step 4:**
```
### Special case: Harness collateral damage found

If Step 3 found new failures that you chose not to fix (Option B.2 or B.3), the code review checklist adds:

- [ ] Failures documented in roadmap with test names
- [ ] Root cause of collateral damage explained or marked "unknown"
- [ ] Follow-up ticket created (if applicable)
- [ ] Developer explicitly acknowledged the trade-off

**Note:** This review step is mandatory. Code cannot be merged without acknowledging collateral damage.
```

---

### Change 4: Strengthen merge gate (Step 5)

**Location:** Stage 5, Step 5 (Commit and merge)

**Add before merge:**
```
### Pre-merge verification

Before the PR can merge, confirm all three:

1. **Test status:** Step 2 → `done` (implementation test passes)
2. **Suite status:** Step 3 → `done` (suite is clean OR failures confirmed pre-existing)
3. **Review status:** Step 4 → `done` (code review passed, including collateral damage acknowledgment if any)

If ANY step is not `done`, the PR cannot merge. Update the blocker and ask the developer to fix it.
```

---

### Change 5: Update roadmap template with harness build tracking

**Location:** Stage 3 (Roadmap generation)

**Current roadmap table:**
```
| # | Step | File(s) | Done when | Status |
|---|------|---------|-----------|--------|
| 1 | [Write test — see harness or Spring Boot rules below] | [test file path] | [test command] → RED (failing, expected) | next |
| 2 | [Implement the change — be specific, name the method] | [impl file path] | [same test command] → GREEN | next |
| 3 | Run full suite | [module or test dir] | [suite command] → no new failures | next |
| 4 | Code review | PR diff | All AVOD checklist items pass (see Stage 5) | next |
| 5 | Merge + verify | master / main | PR merged; [INT or staging] confirms expected behavior | next |
```

**Add to harness-specific repos (director2-aws):**
```
| # | Step | File(s) | Done when | Status |
|---|------|---------|-----------|--------|
| 1 | Write harness XML test | suite/<module>/test/<name>.xml | Test runs and fails (RED) | next |
| 2a | [Optional] Build harness image | buildenv + ./gradlew + ./build-harness-mysql-image.sh | Developer chooses: manual, auto, or skip | next |
| 2b | Implement the change | [impl file path] | Specific test passes (GREEN) | next |
| 3 | Run full suite + assess failures | [module or test dir] | Suite is clean OR failures confirmed pre-existing (documented) | next |
| 4 | Code review (with collateral damage check) | PR diff | All AVOD checklist items pass; collateral damage (if any) acknowledged | next |
| 5 | Merge + verify | master / main | PR merged; INT/staging confirms expected behavior | next |

**Risks**

| Risk | Caught by | Mitigation |
|------|-----------|-----------|
| Harness image stale, tests fail spuriously | Step 2a (buildenv) | Developer can manually rebuild or use auto option |
| Unrelated tests break (collateral damage) | Step 3 (full suite) | Pre-existing failure check; separate ticket option |
| Code review misses collateral damage implications | Step 4 | Explicit checklist item for damage acknowledgment |
| Changes merge without clean suite | Step 5 gate | Pre-merge verification blocks unless Step 3 is done |
```

---

### Change 6: Update completion report to show harness decisions

**Location:** Stage 6 (Completion Report)

**Add new section:**
```markdown
## Harness Build Decisions

**Build option chosen:** [Manual / Automated / Skipped]

If automated:
- buildenv setup: [successful / failed — reason]
- ./gradlew clean build: [successful / failed — reason]
- ./build-harness-mysql-image.sh: [successful / failed — reason]

**Full suite results:**
- Status: [Clean / Pre-existing failures / New failures]
- If failures: [List of tests, whether pre-existing confirmed, developer action taken]
- Collateral damage: [None / [Details], addressed in [separate ticket or this PR]]

**Code review findings:**
- AVOD checklist: [N items passed, M items failed initially, all resolved]
- Collateral damage acknowledgment: [Yes / N/A]
```

---

## Implementation Plan

1. **Update Stage 5, Step 2:** Add buildenv options (manual/auto/skip)
2. **Update Stage 5, Step 3:** Add collateral damage detection and decision tree
3. **Update Stage 5, Step 4:** Add collateral damage acknowledgment to checklist
4. **Update Stage 5, Step 5:** Add pre-merge verification gate
5. **Update Stage 3 roadmap template:** Add Step 2a for buildenv; update risks
6. **Update Stage 6 completion report:** Add harness decisions section
7. **Add to AVOD Domain Reference:** Buildenv commands and collateral damage patterns
8. **Validation:** Script validates that roadmap Step 3 is marked `done` or `partial` with documentation before merge allowed

---

## Testing Strategy

**Unit/Integration tests** (N/A — skill is documentation)

**Manual validation** (per ticket):
1. Run skill on a practice director2-aws ticket
2. Choose each buildenv option: manual, auto, skip
3. Trigger collateral damage scenario (implement change that breaks unrelated test)
4. Verify developer can choose: fix, separate ticket, or acknowledge skip
5. Confirm completion report documents the decision
6. Verify pre-merge gate blocks if Step 3 is not `done`

**Acceptance criteria per stage:**
- Stage 5, Step 2: Developer choice respected; auto option completes without error
- Stage 5, Step 3: Collateral damage detected; pre-existing check works; decision tree guides developer
- Stage 5, Step 4: Code review includes collateral damage acknowledgment
- Stage 5, Step 5: Merge blocked if Step 3 not done
- Stage 6: Report documents harness decisions and any collateral damage

---

## Boundaries

**Always:**
- Document whether suite is clean or has pre-existing/new failures
- Block merge if Step 3 not marked `done`
- Show collateral damage findings before asking developer to proceed
- Require explicit acknowledgment of any trade-offs

**Ask first:**
- Whether to automate buildenv (Option 2)
- How to handle new suite failures (fix, separate ticket, or skip)
- Whether pre-existing failures need confirmation

**Never:**
- Silently merge with unknown suite state
- Skip collateral damage check
- Mark Step 3 done without clean suite or documented pre-existing failures
- Proceed to Step 5 (merge) if any earlier step is blocked
