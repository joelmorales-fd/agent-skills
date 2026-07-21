---
description: Review implementation for scope creep — detect drift, new abstractions, structural changes
---

Invoke the agent-skills:scope-guardian skill.

Compare what was asked against what was delivered. Audit for:

1. **New abstractions** — classes, interfaces, protocols not in the original request
2. **Data reshaping** — type changes without explicit approval
3. **Structural changes** — hierarchy flattening or deepening
4. **Spaghetti patterns** — tangled dependencies, unclear boundaries
5. **Feature creep** — functionality beyond what was asked

Compare the implementation against the original task scope.
Output a scope report with verdicts: CLEAN, DRIFT, or VIOLATION.
