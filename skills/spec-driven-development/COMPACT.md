---
name: spec-driven-development
mode: compact
---

# spec-driven-development — Compact

## Trigger
- New project, feature, or significant change
- Requirements unclear or missing
- Change touches multiple files

## Process
1. **SPECIFY**: Write spec covering 6 areas (Objective, Commands, Structure, Style, Tests, Boundaries)
2. **PLAN**: Technical implementation plan with risks and order
3. **TASKS**: Break into units <5 files each with acceptance criteria
4. **IMPLEMENT**: Execute via incremental-implementation + test-driven-development

## Hard Rules
- NO CODE until spec is approved by human
- Surface assumptions before proceeding:
  ```
  ASSUMPTIONS I'M MAKING:
  1. [assumption]
  → Correct me now or I'll proceed.
  ```
- Each phase needs human sign-off before next

## Gate
Spec saved to `docs/specs/[name].md` and human says "approved"

## Spec Areas (Brief)
1. **Objective**: What + why + who + success criteria
2. **Commands**: Build, test, lint, dev (full commands)
3. **Structure**: Directory layout
4. **Style**: One code example showing conventions
5. **Testing**: Framework, locations, coverage expectations
6. **Boundaries**: Always do / Ask first / Never do

## Output
`docs/specs/[name].md`

---

→ **Full guidance**: `skills/spec-driven-development/SKILL.md`
