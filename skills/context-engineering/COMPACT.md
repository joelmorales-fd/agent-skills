---
name: context-engineering
mode: compact
---

# context-engineering — Compact

## Trigger
- Starting a new coding session
- Agent output quality is declining
- Switching between different parts of codebase
- Setting up a new project for AI-assisted development

## Context Hierarchy (Most → Least Persistent)
```
┌─────────────────────────────────────┐
│  1. Rules Files (CLAUDE.md)         │ ← Always loaded
├─────────────────────────────────────┤
│  2. Spec / Architecture Docs        │ ← Per feature
├─────────────────────────────────────┤
│  3. Relevant Source Files           │ ← Per task
├─────────────────────────────────────┤
│  4. Error Output / Test Results     │ ← Per iteration
├─────────────────────────────────────┤
│  5. Conversation History            │ ← Compacts over time
└─────────────────────────────────────┘
```

## Hard Rules
- **Context starvation → hallucination**: Always load rules + relevant files
- **Context flooding → lost focus**: Keep <2,000 lines per task
- **Surface confusion explicitly**: Don't silently guess when requirements conflict
- **Fresh session** when switching between major features

## Pre-Task Context Loading
1. Read the file(s) you'll modify
2. Read related test files
3. Find one example of similar pattern in codebase
4. Read type definitions involved

## When Context Conflicts
```
CONFUSION:
Spec says X, but existing code does Y.

Options:
A) Follow spec (may need to update code)
B) Follow existing pattern (may need to update spec)
C) Ask (this needs human decision)

→ Which approach?
```

## Anti-Patterns
| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Context starvation | Agent invents APIs | Load rules + source files |
| Context flooding | Agent loses focus | <2,000 lines per task |
| Stale context | References deleted code | Fresh session |
| Silent confusion | Agent guesses wrong | Surface ambiguity explicitly |

## Context Overflow Prevention

| Turns | Action |
|-------|--------|
| ~20 | Warn: Consider `/compact` |
| ~30 | Recommend: `/checkpoint` or `/compact` |
| ~40 | Stop: Require action |

## Memory vs Handoffs

| Need | Use |
|------|-----|
| Knowledge survives all sessions | `/memories/` (user/repo memory) |
| Task state for next session | `.handoff/` (via /checkpoint) |
| Just reduce context now | `/compact` |

**Memory paths:**
- `/memories/` — User preferences, patterns (persistent)
- `/memories/repo/` — Project conventions, commands (repo-scoped)
- `.handoff/` — Session checkpoints (task-scoped)

---

→ **Full guidance**: `skills/context-engineering/SKILL.md`
