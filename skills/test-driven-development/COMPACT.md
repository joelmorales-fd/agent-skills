---
name: test-driven-development
mode: compact
---

# test-driven-development — Compact

## Trigger
- Implementing any new logic or behavior
- Fixing any bug (use Prove-It Pattern)
- Modifying existing functionality

## Process (The Cycle)
```
    RED ──────→ GREEN ──────→ REFACTOR ──→ (repeat)
     │            │              │
     ▼            ▼              ▼
  Test FAILS  Test PASSES   Tests still PASS
```

1. **RED**: Write a test that fails (test MUST fail first)
2. **GREEN**: Write minimal code to make it pass (no more)
3. **REFACTOR**: Clean up with tests green
4. **REPEAT**

## Bug Fix: Prove-It Pattern
```
Bug report arrives
       │
       ▼
Write test that demonstrates the bug
       │
       ▼
Test FAILS (confirming bug exists)
       │
       ▼
Implement the fix
       │
       ▼
Test PASSES (proving fix works)
       │
       ▼
Run full suite (no regressions)
```

## Hard Rules
- Test **MUST fail** before you write implementation
- **Test state, not interactions** (what it does, not how)
- **Mock at boundaries only**: DB, HTTP, filesystem — not internal functions
- **DAMP over DRY** in tests: Readability > deduplication

## Test Pyramid
```
     ╱╲      E2E (~5%) — Critical flows only
    ╱──╲     Integration (~15%) — API boundaries
   ╱────╲    Unit (~80%) — Pure logic, milliseconds
```

## Gate
All tests pass before commit

---

→ **Full guidance**: `skills/test-driven-development/SKILL.md`
