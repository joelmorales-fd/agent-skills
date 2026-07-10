# AVOD Ticket Skill — Complete Guide

**Quick summary:** This skill guides you step-by-step from a raw Jira ticket to merged, tested code. It asks clarifying questions, documents your plan before any code is written, enforces testing rigorously, and handles the messy parts (like unrelated test failures) with clear decision points. **All guidance uses numbered selections — just type a number instead of typing full responses.**

---

## The Six Stages: From Ticket to Deployed

```
INTAKE → INVESTIGATION → ROADMAP → CODE GUIDE → IMPLEMENT → REPORT
```

Each stage produces a document and/or verified result. **No code is written until Stage 3 (the roadmap) is approved.**

---

## Stage 1: Ticket Intake — Understand "Done"

**What happens:** You paste your Jira ticket (or give a URL), and the skill asks five clarifying questions.

**Questions you'll answer:**
1. **Which repo?** Choose from director2-aws, moneyball-aws, fw-catalogsync-aws, or other
2. **What kind of change?** Bug fix, behavior change, new feature, or config
3. **What does "done" look like?** What API endpoint changes? What should it return?
4. **Constraints?** Backwards compatibility, no-touch zones, deployment order?
5. **Prior context?** Related tickets, existing investigations, Slack threads?

**Decision point:** 
```
Does this scope look right?
1 Yes — save and proceed
2 No — let me refine
3 Refine — show me what to change
```

**Output:** Scope statement saved. No code yet.

---

## Stage 2: Investigation — Map the Code (Real quotes, not guesses)

**What happens:** The skill reads the files you name, follows imports and references, and builds a map of what needs to change.

**You'll see:**
- Exact file paths and line numbers of code that needs changing
- What's currently broken or missing (quoted directly from the code)
- Existing helpers or patterns you should reuse (not reinvent)
- Specific table of files and their line numbers

**Quality bar:** Every reference is verified by reading the actual file. No "probably" or "I think". If you see those words, ask for clarification.

**Decision point:**
```
Does this investigation look accurate?
1 Yes — save and proceed
2 No — something's missing
3 Refine — show specific issues
4 Back — return to Stage 1
```

**Output:** Investigation document with quoted code. Still no implementation.

---

## Stage 3: Roadmap (Living Plan) — Get Approval Before Code

**What happens:** The skill generates a 5-step plan with specific done-criteria. You review and approve before any code is written.

**Your plan will include:**

| Step | What | Done when |
|------|------|-----------|
| 1 | Write test (harness XML or integration test) | Test fails (RED) as expected |
| 2 | Implement the change | Test passes (GREEN) |
| 3 | Run full suite | Suite is clean OR pre-existing failures confirmed |
| 4 | Code review | AVOD checklist passes |
| 5 | Merge + verify | INT/staging confirms behavior |

**Key feature:** For director2-aws repos, Step 1 is **always a harness test written before any Java changes**.

**Decision point:**
```
Does this plan look right?
1 Yes — save and proceed
2 No — something's wrong
3 Back — return to Stage 2
```

**Gate:** **Nothing happens until you approve this plan.** Once approved, you proceed to implementation.

**Output:** Roadmap saved. This document is "living" — you'll update step statuses as you work.

---

## Stage 4: Code Guide + Test Plan — Exact Instructions

**What happens:** You get a detailed guide that says exactly which files to change, which methods to modify, and what tests to write (before implementation).

**You'll see:**
- Exact file paths and line numbers
- Specific methods to change
- Code patterns to follow (with examples from existing code)
- What NOT to change (scope creep prevention)
- Detailed test cases with inputs and expected outputs

**No gate here — this feeds directly into Stage 5.**

---

## Stage 5: Implement + Verify — Where the Work Happens

### Step 5.1: Write the test first
Write the test file (harness XML or integration test) and run it.

**Expected result:** RED (failing). If it passes immediately, the test is wrong.

**When done:** Update roadmap Step 1 → `done`

### Step 5.2: Implement + Choose your build approach (director2-aws only)

You make the code changes. After each iteration, **you choose how to build the harness:**

```
How would you like to build the harness?

1 Manual — I'll run buildenv steps myself
  Use when: You want full control; debugging build issues
  
2 Automated — Run buildenv for me
  Use when: First-time build; want hands-off automation
  
3 Skip — Use existing image
  Use when: Image is fresh; iterating rapidly on code

→ Choose [1-3]:
```

**What each option means:**

- **Manual (1):** You run buildenv yourself inside Docker, compile, create the harness image, then run the test from the host
- **Automated (2):** Skill handles the buildenv, compile, and image creation — you just monitor
- **Skip (3):** Uses the harness image you already have (fast iteration, but may fail if image is stale)

**When done:** Test passes (GREEN). Update roadmap Step 2 → `done`

### Step 5.3: Run the full suite — Handle failures clearly

You run the entire suite for your module. This catches "collateral damage" — unrelated tests that break because of your changes.

```bash
./run-harness-sidecar.sh -p -m -t 10 <module>
```

**If suite is clean:** Mark Step 3 → `done`, proceed to code review.

**If failures appear:**

```
Which best describes these failures?

1 Pre-existing (not caused by my change)
  Evidence: Test fails on main branch too (you'll verify this now)
  
2 New (caused by my change — fix now)
  Action: Fix the root cause; re-run suite until clean
  
3 New (caused by my change — separate ticket)
  Action: File new Jira ticket for the collateral damage
  
4 New (caused by my change — skip for now)
  Warning: Requires explicit acknowledgment in code review
  Use only if: You understand the impact and accept the trade-off

→ Choose [1-4]:
```

**What each choice does:**

- **Pre-existing (1):** Skill verifies the test fails on main too. Document it. Mark Step 3 → `done`.
- **Fix now (2):** Fix the root cause, re-run suite. Loop until clean.
- **Separate ticket (3):** File a Jira ticket. Skill documents it in the roadmap. Mark Step 3 → `done` with caveat.
- **Skip (4):** Document the failures. **Must be explicitly acknowledged in code review before merge.**

### Step 5.4: Code review — AVOD checklist

Skill runs the AVOD checklist against your diff:

**Authentication & session:**
- authUserId checked for null before use
- Anonymous, non-AVOD, and AVOD sessions handled separately
- Non-AVOD behavior unchanged

**Redis:**
- TTL set explicitly (no unbounded entries)
- No stale cache after the change
- Key naming follows conventions

**Tests:**
- Happy path, error case, edge case covered
- No hardcoded user IDs or production data
- Test setup uses fake-create ops

**Code quality:**
- Helpers don't duplicate existing code
- Pattern matches existing Ops in the module
- Only named files changed (no scope creep)

**Harness suite (director2-aws only):**
- Suite clean OR pre-existing failures documented
- If collateral damage: root cause identified, separate ticket filed, developer acknowledges trade-off

```
Does the code review pass?
1 Yes — all items pass
2 No — some items need fixing
```

When all items pass, mark Step 4 → `done`.

### Step 5.5: Commit and merge — Pre-merge gate

Before merge, skill confirms all three:

1. ✅ **Test status:** Step 2 → `done` (implementation test passes)
2. ✅ **Suite status:** Step 3 → `done` (clean OR pre-existing confirmed)
3. ✅ **Review status:** Step 4 → `done` (checklist passed)

If any are not `done`, merge is blocked. Fix the blocker first.

```
Ready to commit?
1 Yes — commit and merge
2 No — pause
```

---

## Stage 6: Completion Report — Honest Record

**What happens:** Skill generates a report that documents what was planned vs. what actually happened.

**Report includes:**
- What the AI did (stage-by-stage: which files were read, what was found)
- What you did (wrote test, implemented change, chose buildenv option, handled suite failures)
- Plan vs. actual (any deviations and why)
- Harness build decisions (buildenv option chosen, suite results, collateral damage handling)
- Retro notes (what worked well, what was hard, patterns to remember)

**Decision point:**
```
Does this report look accurate?
1 Yes — complete
2 No — needs correction
```

**Output:** Completion report saved. Ticket is done.

---

## Real Example Workflow

### Scenario: Fix bug in AVOD session detection (director2-aws)

**Stage 1:** Paste ticket, answer 5 questions
- Repo: director2-aws
- Type: Bug fix
- Done when: AVOD-eligible users see correct session type in API response
- Constraints: Must not affect non-AVOD users
- Prior context: Slack thread in #avod-engineering

**Output:** Scope statement

---

**Stage 2:** Skill investigates
- Reads `AccountMapDef.java` — finds session type check at line 67
- Reads `SomeOp.java` — finds where session type is used (lines 120–145)
- Reads `SomeOpTest.xml` — finds existing harness test structure
- Quotes: "Line 67 checks `isAvodAnonymousSession()` but does not verify eligibility status"

**Output:** Investigation with file paths and line numbers

---

**Stage 3:** Skill generates roadmap

| Step | What | Done when |
|------|------|-----------|
| 1 | Write harness test for AVOD session detection | Test fails (RED) |
| 2 | Fix session type check in AccountMapDef.java:67 | Test passes (GREEN) |
| 3 | Run full suite for media2 module | Clean or pre-existing failures confirmed |
| 4 | Code review — AVOD checklist | All items pass |
| 5 | Merge + verify in INT | INT confirms correct session type returned |

**Your decision:** ✅ Yes, proceed

---

**Stage 4:** Skill provides code guide
- "Modify `AccountMapDef.isAvodAnonymousSession()` to check eligibility flag before returning true"
- Test plan: "Input: AVOD user with eligibility flag set. Expected: session type = AVOD. Input: same user with flag unset. Expected: session type = non-AVOD"

---

**Stage 5:** You implement

**Step 5.1:** Write harness XML test
```bash
./run-harness-sidecar.sh -p -t 1 -j 2048 /media2/test/test-session-detection.xml
# Result: RED ✓
```

**Step 5.2:** Implement fix, choose build approach
```
How would you like to build the harness?
1 Manual (you know Docker + gradlew)
→ Choose [1]: 1
```

You run buildenv, compile, create harness image, run test. Test passes (GREEN) ✓

**Step 5.3:** Run full suite
```bash
./run-harness-sidecar.sh -p -m -t 10 media2
# Result: 2 failures in unrelated tests
```

```
Which best describes these failures?
1 Pre-existing? 2 Fix now? 3 Separate ticket? 4 Skip?
→ Choose: 1
```

You verify on main: same 2 failures exist. Documented ✓

**Step 5.4:** Code review
- ✅ authUserId null checks in place
- ✅ AVOD/non-AVOD sessions handled separately
- ✅ Non-AVOD behavior unchanged
- ✅ Test covers happy path + edge case
- ✅ Pre-existing failures documented

All pass ✓

**Step 5.5:** Merge
```
Ready to commit?
→ Choose: 1
```

Committed, PR merged, INT confirms session type. ✓

---

**Stage 6:** Completion report
Documents: what was read, what was fixed, which failures were pre-existing, how buildenv was handled, all steps completed.

---

## Key Features

### ✅ Numbered selections (no typing)
Every decision uses `→ Choose [1-N]:` format. Just type a number instead of typing "yes" or "fix-now".

### ✅ Three buildenv options (director2-aws only)
- **Manual:** Full control, useful for debugging
- **Automated:** Hands-off, useful for first-time builds
- **Skip:** Fast iteration when image is fresh

### ✅ Four ways to handle collateral damage
- Pre-existing (verify, document, proceed)
- Fix now (loop until clean)
- Separate ticket (document, proceed)
- Skip (acknowledge in code review, proceed with caution)

### ✅ Pre-merge gate
Merge is blocked if test fails, suite has undocumented failures, or code review didn't pass.

### ✅ Real code quoted
Every finding includes file paths and line numbers. No "probably" or guesses.

### ✅ Living roadmap
Status updates as you work. Always shows what's done, what's next, what's blocked.

---

## When to Use This Skill

**Use when:**
- You have a Jira ticket and need to go from understanding to merged code
- You're working in director2-aws, moneyball-aws, fw-catalogsync-aws, or similar AVOD repos
- You want step-by-step guidance with clear gates and approval points
- You need to document your decisions (why you chose this buildenv approach, how you handled failures)

**Don't use when:**
- One-line fix or config-only change
- Scope is already fully understood and a plan exists
- You just need help with a specific piece of code

---

## Tips for Success

1. **Answer Stage 1 questions carefully.** They drive everything downstream. If you're unsure, ask for refinement.

2. **Read the investigation carefully.** If you see "probably" or "I think", ask for clarification. Every reference should be verified from actual code.

3. **Approve the roadmap before writing any code.** The gates are there to prevent wasted rework.

4. **Test first, implement second.** RED test before any code changes. This ensures you're testing something new, not existing behavior.

5. **Don't skip the full suite (Step 3).** It catches collateral damage early. If failures appear, make a clear decision: fix, ticket, or acknowledge.

6. **Buildenv choice depends on your situation:**
   - Manual if you're debugging or want full control
   - Automated if building for the first time
   - Skip if you know the image is fresh and you're iterating fast

7. **Collateral damage is normal.** It's not a blocker. Just document it and make a clear choice (fix, separate ticket, or acknowledge).

---

## Documents You'll Have When Done

```
01-scope.md              ← What problem are we solving?
02-investigation.md      ← What code needs to change?
03-roadmap.md            ← Step-by-step plan (updated as you work)
04-code-guide.md         ← Exact code changes + test plan
05-implementation-log.md ← Test results, checklist, commit hash
06-completion-report.md  ← Honest record of what happened
```

All saved to your chosen directory (defaults to repo root).

---

## Questions?

**"Can I go back and change something?"** Yes. The skill supports refinement at every stage. Just choose the "no, refine" or "back" option and update.

**"Do I have to follow every step?"** No skipping. Stages 1–3 produce documents that must be approved before moving forward. This prevents wasted rework.

**"What if the test fails unexpectedly?"** Loop back to Step 5.3 (run full suite). If it's collateral damage, choose your path: fix, separate ticket, or acknowledge.

**"Can I use automated buildenv?"** Yes, if you're in director2-aws. It's option 2 in Step 5.2.

**"What if the suite has pre-existing failures?"** Verify them on main branch. Document in the roadmap. Proceed.

---

**Ready to start?** Open a Jira ticket and invoke `/avod`. The skill will take it from there.
