---
name: debugging-and-error-recovery
mode: compact
---

# debugging-and-error-recovery — Compact

## Trigger
- Tests fail after a code change
- Build breaks
- Runtime behavior doesn't match expectations
- Bug report arrives
- Error in logs or console

## Process (The Triage)
```
1. STOP ──→ 2. REPRODUCE ──→ 3. LOCALIZE ──→ 4. REDUCE
                                                  │
7. RESUME ←── 6. GUARD ←── 5. FIX ←──────────────┘
```

1. **STOP**: Don't add features. Preserve evidence (error output, logs, repro steps)
2. **REPRODUCE**: Make the failure happen reliably. Can't reproduce = can't fix with confidence
3. **LOCALIZE**: Which layer is failing?
   - UI/Frontend → console, DOM, network tab
   - API/Backend → server logs, request/response
   - Database → queries, schema, data
   - Build → config, dependencies
   - External → connectivity, API changes
4. **REDUCE**: Create minimal failing case. Strip away unrelated code.
5. **FIX**: Root cause, NOT symptom
6. **GUARD**: Write regression test that catches this specific failure
7. **RESUME**: Only after verification passes

## Hard Rules
- **Don't push past failing tests** to work on next feature
- **Fix root cause**, not symptom:
  ```
  Symptom fix (bad):  Deduplicate in UI
  Root cause fix:     Fix the SQL JOIN that produces duplicates
  ```
- **Use git bisect** for regressions: `git bisect start` / `bad` / `good`
- **Ask "Why?" repeatedly** until you reach actual cause

## Non-Reproducible Bugs
- Timing-dependent? → Add timestamps, artificial delays
- Environment-dependent? → Compare versions, env vars
- State-dependent? → Check for leaked state, globals

## Gate
Test suite passes AND new regression test exists

---

→ **Full guidance**: `skills/debugging-and-error-recovery/SKILL.md`
