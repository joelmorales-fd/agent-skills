---
name: code-review-and-quality
mode: compact
---

# code-review-and-quality — Compact

## Trigger
- Before merging any PR or change
- After completing a feature implementation
- When reviewing code from another agent or human

## Process: The Five Axes

Review every change across these dimensions:

### 1. Correctness
- Does it do what the spec/task says?
- Edge cases handled (null, empty, boundary)?
- Tests actually test the right things?

### 2. Readability
- Can another engineer understand without explanation?
- Names descriptive? Control flow straightforward?
- Could this be simpler?

### 3. Architecture
- Follows existing patterns or justified new one?
- Clean module boundaries? No circular deps?
- Abstraction level appropriate?

### 4. Security
- User input validated at boundaries?
- Secrets out of code/logs?
- Auth/authz checked? Queries parameterized?

### 5. Performance
- N+1 queries? Unbounded loops?
- Missing pagination? Unnecessary re-renders?

## Categorize Findings

| Prefix | Meaning | Action Required |
|--------|---------|-----------------|
| **Critical** | Blocks merge | Must fix (security, data loss) |
| **Important** | Should fix | Missing test, bad abstraction |
| **Nit** | Minor | Style preference, optional |
| **FYI** | Informational | No action needed |

## Hard Rules
- **Approve if it improves codebase**, even if not perfect
- **Include one positive observation** (what's done well)
- **All Critical issues resolved** before merge
- **Target ~100-300 lines per change** (larger = split it)

## Output Template
```markdown
## Review Summary
**Verdict:** APPROVE | REQUEST CHANGES

### Critical Issues
- [File:line] [Issue and fix]

### Important Issues  
- [File:line] [Issue and fix]

### Suggestions
- [File:line] [Suggestion]

### What's Done Well
- [Positive observation]
```

---

→ **Full guidance**: `skills/code-review-and-quality/SKILL.md`
