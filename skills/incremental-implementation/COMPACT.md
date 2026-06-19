---
name: incremental-implementation
mode: compact
---

# incremental-implementation — Compact

## Trigger
- Implementing any multi-file change
- Building from a task breakdown
- Tempted to write >100 lines before testing

## Process (The Cycle)
1. **IMPLEMENT**: Smallest complete piece of functionality
2. **TEST**: Run the test suite
3. **VERIFY**: Tests pass, build clean
4. **COMMIT**: Save progress with descriptive message
5. **NEXT**: Move to next slice (repeat)

```
Implement → Test → Verify → Commit → Next slice
    ↑                                    │
    └────────────────────────────────────┘
```

## Hard Rules
- **One thing at a time**: Don't mix concerns in one change
- **Keep it compilable**: Project must build after each slice
- **Simplicity first**: "What's the simplest thing that could work?"
- **Scope discipline**: Touch ONLY what the task requires
- **Don't clean up adjacent code**: Note it, don't fix it

```
NOTICED BUT NOT TOUCHING:
- [issue outside scope]
→ Want me to create a task for this?
```

## Slicing Strategies
- **Vertical slices** (preferred): One complete path through stack
- **Contract-first**: Define interface, then parallelize
- **Risk-first**: Tackle riskiest piece first

## Gate
Each slice: tests pass AND build succeeds before moving on

---

→ **Full guidance**: `skills/incremental-implementation/SKILL.md`
