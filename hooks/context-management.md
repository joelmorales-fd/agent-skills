# Context Management Hooks

Automatic triggers for maintaining session quality.

---

## Turn Count Enforcement

The `turn-guard.sh` Stop hook automatically tracks turns and enforces limits:

| Turns | Action |
|-------|--------|
| 40+ | Note: "Consider /compact soon" |
| 50+ | Warning: "Consider running /compact" |
| 70+ | Critical: "Run /compact soon or start fresh" |

No manual tracking required — the hook reads the transcript file automatically.

---

## Handoff Triggers

Suggest a handoff when ANY of these conditions is true:

| Trigger | Threshold | Detection |
|---------|-----------|-----------|
| Context fill | >70% | Agent notices slow responses, asks "did I mention this?" |
| Turn count | >50 turns | Count exchanges in conversation |
| Session duration | >2 hours | Track elapsed time |
| Quality degradation | Any sign | Agent forgets rules, re-asks answered questions |
| Feature switch | Major shift | Different area of codebase, new feature entirely |

### Quality Degradation Signs
- Agent asks question that was already answered
- Agent suggests approach that was already rejected
- Agent "forgets" constraints from spec
- Agent proposes code that conflicts with established patterns
- Responses become slower or less focused

---

## Auto-Suggest Protocol

When a trigger is detected, agent should:

```markdown
---
⚠️ **Session Checkpoint Recommended**

Detected: [trigger reason]

Options:
1. **Handoff now** — I'll create a handoff document, then start fresh session
2. **Continue 10 more turns** — Set a reminder for imminent handoff
3. **Ignore** — Continue without checkpoint (quality may degrade)

Which option?
---
```

---

## Mode Selection Rules

### When to Use Full SKILL.md
- First time using a skill in session
- Skill application is complex or nuanced
- Agent made an error related to the skill
- User asks detailed "how" questions

### When to Use COMPACT.md (Digest)
- Skill already used earlier in session
- Quick reference needed during execution
- Multiple skills in play simultaneously
- Context is >50% full

### When to Use Minimal (Inline)
- Context critical (>80% full)
- Simple, well-understood task
- Agent has demonstrated skill mastery
- Near end of session with handoff pending

---

## Session Start Protocol

At the start of each session:

1. **Check for existing handoff**
   ```
   Is there a handoff document for this project/feature?
   → Yes: Load it first, follow resume instructions
   → No: Proceed with normal context loading
   ```

2. **Load compact context**
   ```
   Load compact/_all-compact.md (~2,500 tokens)
   This provides skill digests for entire session
   ```

3. **Load project context**
   ```
   Read CLAUDE.md (project rules)
   Read relevant spec/plan if feature work
   Check for uncommitted changes
   ```

---

## Context Budget Guidelines

| Content Type | Budget | Notes |
|--------------|--------|-------|
| Skills (compact) | 5% | Load _all-compact.md at session start |
| Skills (full) | 15% max | Only expand when needed |
| Project rules | 5% | CLAUDE.md, etc. |
| Spec/plan | 10% | Current feature only |
| Source files | 30-40% | Files being modified |
| Test output | 10-15% | Recent runs only |
| Conversation | 20-30% | Compresses over time |
| **Reserve** | 10% | For unexpected needs |

---

## Handoff Creation Flow

When handoff is triggered and user agrees:

1. **Summarize state**
   - Current skill/phase
   - Active task and progress
   - Files modified
   - Uncommitted changes

2. **Capture decisions**
   - What was decided and why
   - What alternatives were rejected

3. **List remaining work**
   - Tasks not yet done
   - Blocked items and why

4. **Write resume instructions**
   - Exact next step
   - Commands to verify state
   - Context to load

5. **Save handoff**
   - Path: Project's `.handoff/` directory
   - Filename: `{feature}-{date}.md`

6. **Suggest action**
   ```
   Handoff created: .handoff/auth-feature-2024-01-15.md
   
   Next steps:
   1. Review the handoff for accuracy
   2. Commit current changes (or stash)
   3. Start new session
   4. Load handoff as first context
   ```

---

## Recovery Hooks

### If Session Was Interrupted (no handoff)

Try to reconstruct state:
1. Check `git status` and `git diff`
2. Check recent commits: `git log --oneline -10`
3. Look for TODO comments added during session
4. Check for any `.handoff/*.md` files
5. Ask user for context about where they were

### If Handoff Is Stale

Signs a handoff may be outdated:
- Files mentioned don't exist
- Tests fail unexpectedly
- Code has changed since handoff date

Action: Ask user to confirm state before proceeding.

---

## Integration Points

### For Claude Code / Claude.ai
Add to your CLAUDE.md:
```markdown
## Context Management

- At session start, load `compact/_all-compact.md`
- Suggest handoff when context >70% or turns >30
- For handoffs, use template from `handoff/_template.md`
- Store handoffs in project `.handoff/` directory
```

### For VS Code / Copilot
Include in your system prompt or instructions file:
```markdown
When session quality degrades or context fills up,
suggest creating a handoff document for session continuity.
Reference agent-skills/handoff/ for templates.
```

### For Other Agents
Integrate these rules into your agent configuration or system prompt.
