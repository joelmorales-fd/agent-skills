# Skill Loading Protocol

This document tells agents how to use the compact loading system for optimal context efficiency.

---

## How This Works

The `compact/` directory contains **digests** — condensed summaries of full skills.

| Mode | Size | Tokens | Use When |
|------|------|--------|----------|
| **Digest** | ~50 lines | ~200 | Default for most work |
| **Full** | ~300 lines | ~1,200 | First use, complex cases, need templates |
| **Minimal** | ~5 lines | ~30 | Context emergency |

**Default behavior**: Load digests. Expand to full only when needed.

---

## Loading Rules

### Rule 1: Start with Digests

At session start, load `compact/_all-compact.md`. This gives all skill summaries in ~2,500 tokens instead of ~25,000 tokens.

```
"Loading skill reference..."
[Read compact/_all-compact.md]
```

### Rule 2: Expand on First Use (Optional)

When using a skill for the **first time in a complex session**, consider loading the full version:

```
"Loading full guidance for [skill-name]..."
[Read skills/[skill-name]/SKILL.md]
```

After orientation, return to digest mode.

### Rule 3: Use Digest for Established Work

Once familiar with a skill's flow, the digest has everything needed:
- Process steps
- Hard rules (must not violate)
- Gate conditions
- Pointer to full skill

### Rule 4: Expand for Edge Cases

If the digest doesn't cover your situation:
1. Note: "This needs full skill guidance"
2. Load the full SKILL.md
3. Find the relevant section
4. Apply it
5. Return to digest mode

---

## Context Management

### Track Active Skills

At the end of complex work, mentally note:
```
SKILL STATE:
- Active: incremental-implementation (digest mode)
- Phase: IMPLEMENT, slice 3 of 5
- Next: Write tests for login endpoint
```

### Monitor Context Pressure

Suggest handoff when ANY is true:
- Context usage >70% (estimate by conversation length)
- Turn count >30
- Session >2 hours
- Quality degrading (agent forgets rules, re-asks questions)

### Handoff Protocol

When context is filling:
1. Offer: "Context is filling up. Create a handoff document?"
2. If yes: Use `handoff/_template.md` structure
3. Save to project's `.handoff/[feature].md`
4. User starts new session
5. Resume: "Continue from .handoff/[feature].md"

---

## Quick Reference

| Situation | Action |
|-----------|--------|
| Session start | Load `compact/_all-compact.md` |
| First use of skill | Consider loading full SKILL.md |
| Familiar with skill | Use digest only |
| Edge case | Load full, find answer, return to digest |
| Context >70% | Suggest handoff OR compress to digests |
| User says "expand" | Load full SKILL.md |
| User says "continue from handoff" | Load handoff, verify state, continue |

---

## File Locations

```
agent-skills/
├── compact/
│   ├── _loader.md          ← You are here
│   ├── _all-compact.md     ← Load at session start
│   └── [skill-name].md     ← Individual digests (optional)
├── handoff/
│   ├── _template.md        ← Handoff structure
│   └── _example.md         ← Filled-in example
├── hooks/
│   └── context-management.md ← Auto-handoff triggers
└── skills/
    └── [skill-name]/
        ├── SKILL.md        ← Full guidance
        └── COMPACT.md      ← Digest (mirrors compact/[skill].md)
```

---

## Loading Examples

### Example: Session Start
```
Agent: [Session begins]
"Loading skill reference for this session..."
[Reads compact/_all-compact.md]
"Ready. I have guidance for all development phases. What are we working on?"
```

### Example: Need Full Template
```
Agent: "The spec digest has the process, but you asked for the full template.
Loading full spec-driven-development..."
[Reads skills/spec-driven-development/SKILL.md]
[Finds template section]
"Here's the full spec template: ..."
```

### Example: Context Pressure
```
Agent: "We're at about 35 turns and I'm noticing my responses getting longer
to maintain context. 

RECOMMENDATION: Create a handoff checkpoint now so we can continue fresh.

Should I create the handoff?"
```
