---
name: code-simplification
mode: compact
---

# code-simplification — Compact

## Trigger
- Code works but is harder to read than needed
- Deeply nested logic, long functions, unclear names
- Reviewing code that accumulated complexity
- Refactoring code written under time pressure

## Five Principles

1. **Preserve Behavior Exactly** — Same outputs, errors, side effects. If unsure, don't change.
2. **Follow Project Conventions** — Match project style, not external preferences.
3. **Clarity Over Cleverness** — Explicit > compact when compact needs mental pause.
4. **Maintain Balance** — Don't over-simplify. Some abstractions exist for good reasons.
5. **Chesterton's Fence** — Understand WHY code exists before removing it.

## The Process

```
1. SCAN → Identify simplification opportunities
2. VERIFY → Ensure test coverage exists (write tests if not)
3. SIMPLIFY → One change at a time, run tests after each
4. REVIEW → Confirm all tests pass, diff is clean
```

## What to Simplify

| Pattern | Simplification |
|---------|---------------|
| Deep nesting | Guard clauses, extract helpers |
| Long functions (>50 lines) | Split by responsibility |
| Nested ternaries | if/else or switch |
| Generic names | Descriptive names |
| Duplicated logic | Shared functions |
| Dead code | Remove (after confirming) |

## Hard Rules

- **Tests MUST pass** after every change
- **Never change behavior** — only how it's expressed
- **Understand before simplifying** — don't touch code you don't understand
- **One change at a time** — easier to revert if tests break

## Anti-Patterns

| Don't | Why |
|-------|-----|
| Simplify for line count | Goal is comprehension, not fewer lines |
| Remove "unnecessary" abstractions | May exist for testability/extensibility |
| Combine unrelated logic | Two simple > one complex |
| Inline named helpers | Names give concepts identity |

## Verification
- All tests pass
- Build succeeds
- Diff is clean (no unrelated changes)
- Code is easier to understand (not just shorter)

---

→ **Full guidance**: `skills/code-simplification/SKILL.md`
