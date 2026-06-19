# Session Handoff Template

Use this template when:
- Context window is filling up (>70%)
- Session has been long (>50 turns or >2 hours)
- Switching to different feature/work
- Ending work session for the day
- Quality is degrading (agent forgets rules, re-asks questions)

**Save handoffs to your project's `.handoff/` directory**, not here.

---

```markdown
# Handoff: [FEATURE NAME]

**Created**: [YYYY-MM-DD HH:MM]
**Session**: [brief identifier]

---

## 1. Current State

### Active Workflow
- **Skill**: [e.g., incremental-implementation]
- **Phase**: [e.g., IMPLEMENT, slice 3 of 5]
- **Mode**: [digest / full]

### Current Task
```
Task: [Description from plan]
Status: [in-progress / blocked / nearly-complete]
Progress: [What's done within this task]
Next step: [The specific next action to take]
```

### Files Modified This Session
| File | Status | Change |
|------|--------|--------|
| `path/to/file.ts` | Created | [Description] |
| `path/to/file.ts` | Modified | [Description] |

### Uncommitted Changes
```bash
# Verified at [time]:
git status
git diff --stat
```

---

## 2. Decisions Made

| # | Decision | Rationale | Rejected Alternative |
|---|----------|-----------|---------------------|
| 1 | [Decision] | [Why] | [What we didn't do] |
| 2 | [Decision] | [Why] | [What we didn't do] |

---

## 3. Context & Constraints

### Confirmed Constraints (from spec/user)
- [Constraint 1]
- [Constraint 2]

### Assumptions (not yet validated)
- [Assumption 1] — To validate: [how]
- [Assumption 2] — To validate: [how]

### Known Issues / Tech Debt
- [Issue discovered but deferred]

---

## 4. Remaining Work

### This Feature
- [ ] **Task N**: [Description] — Accept: [criteria]
- [ ] **Task N+1**: [Description] — Accept: [criteria]
- [ ] **Review checkpoint**

### Blocked Items
| Item | Blocked By | Unblock Action |
|------|------------|----------------|
| [Item] | [Reason] | [What needs to happen] |

---

## 5. Technical Reference

### Patterns Established
```typescript
// Pattern: [Name]
// Used for: [What]
[Code snippet]
```

### Key Files
- `[path]` — [What it does]
- `[path]` — [What it does]

### Commands
```bash
# Verify current state
[test command]

# Build
[build command]
```

---

## 6. Resume Instructions

### Before Coding
1. Read this handoff completely
2. Run verification command: `[command]`
3. Check for uncommitted changes: `git status`

### Load Context
1. Load `compact/_all-compact.md` for skill reference
2. Note active skill: **[skill-name]** in **[phase]**
3. Review "Decisions Made" — don't re-debate these

### Continue From
**Exact next step**: [Precise description]
**Files to touch**: [List]
**Expected outcome**: [What should be true when done]

---

## 7. Compact Skill Reference

### [Active Skill Name]
[Paste relevant section from compact/_all-compact.md]

---

## Verification Checklist (For New Session)

After loading this handoff, confirm:
- [ ] I understand the current task and next step
- [ ] Tests pass when I run the verification command
- [ ] No unexpected uncommitted changes
- [ ] I know which skill/phase I'm in
- [ ] I won't re-debate the decisions listed above
```

---

## Tips for Good Handoffs

### Be Specific
```
❌ "Working on auth"
✅ "Task 3: Login endpoint. JWT generation done, next: session cookie setup"
```

### Include Commands
Don't make next session guess. Include exact verification commands.

### Capture Decisions
Future sessions will wonder "why?" — write it down.

### Keep Skill Reference
Include the compact digest so next session doesn't need to load it.
