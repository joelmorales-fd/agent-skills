---
name: planning-and-task-breakdown
mode: compact
---

# planning-and-task-breakdown — Compact

## Trigger
- Have a spec and need to break it into implementable units
- Task feels too large or vague to start
- Need to estimate scope or parallelize work

## Process

1. **PLAN MODE**: Read-only. No code.
   - Read spec and relevant codebase
   - Map dependencies between components
   - Note risks and unknowns

2. **DEPENDENCY GRAPH**: What depends on what?
   ```
   Database schema
       ├── API models
       │   ├── API endpoints
       │   │   └── Frontend client
       │   └── Validation logic
       └── Migrations
   ```

3. **VERTICAL SLICES** (not horizontal):
   ```
   ❌ Bad: All DB, then all API, then all UI
   ✅ Good: User registration (DB + API + UI for one feature)
   ```

4. **WRITE TASKS**: Each follows this template:
   ```markdown
   ## Task [N]: [Short title]
   
   **Description:** [One paragraph]
   
   **Acceptance criteria:**
   - [ ] [Specific, testable condition]
   
   **Verification:**
   - [ ] Tests pass: `[command]`
   - [ ] Build succeeds: `[command]`
   
   **Files:** [List of files to touch]
   **Size:** [S: 1-2 files | M: 3-5 | L: 5+]
   ```

5. **ORDER & CHECKPOINT**:
   - Foundation first
   - High-risk tasks early (fail fast)
   - Checkpoint every 2-3 tasks

## Task Sizing

| Size | Files | If larger... |
|------|-------|--------------|
| S | 1-2 | ✓ Good |
| M | 3-5 | ✓ Acceptable |
| L | 5-8 | ⚠️ Consider splitting |
| XL | 8+ | ❌ Must split |

## Hard Rules
- No task touches >5 files
- Each task leaves system in working state
- Checkpoint after every 2-3 tasks
- If you write "and" in task title → it's two tasks

---

→ **Full guidance**: `skills/planning-and-task-breakdown/SKILL.md`
