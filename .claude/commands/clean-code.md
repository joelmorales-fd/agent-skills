---
description: Review code for structural violations — hard-coding, god classes, cryptic names, unwanted abstractions
---

Invoke the agent-skills:clean-code-guardian skill.

Audit the current changes (staged files, recent commits, or specified scope) for:

1. **Hard-coded values to pass tests** — magic numbers, test-specific logic
2. **Giant classes/files** — functions >50 lines, classes >300 lines, files >500 lines
3. **Cryptic variable names** — tmp, val, res, x, data
4. **Unwanted abstractions** — new classes, interfaces, protocols not requested
5. **Data reshaping** — changing dict→dataclass, list→tuple without permission
6. **Defensive bloat** — retry logic, fallbacks not in original

Output a violation report with specific file:line references.
