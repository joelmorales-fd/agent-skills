# agent-skills

This is the agent-skills project — a collection of production-grade engineering skills for AI coding agents.

## Project Structure

```
skills/       → Core skills (SKILL.md + COMPACT.md per directory)
compact/      → Token-optimized skill loading (all digests + loader)
handoff/      → Session continuity templates
agents/       → Reusable agent personas (code-reviewer, test-engineer, security-auditor, web-performance-auditor)
hooks/        → Session lifecycle hooks (includes context-management.md)
.claude/commands/ → Slash commands (/spec, /plan, /build, /test, /review, /code-simplify, /ship; plus /webperf specialist audit)
references/   → Supplementary checklists (testing, performance, security, accessibility)
docs/         → Setup guides for different tools
```

## Skills by Phase

**Define:** interview-me, idea-refine, spec-driven-development
**Plan:** planning-and-task-breakdown
**Build:** incremental-implementation, test-driven-development, context-engineering, source-driven-development, doubt-driven-development, frontend-ui-engineering, api-and-interface-design
**Verify:** browser-testing-with-devtools, debugging-and-error-recovery
**Review:** code-review-and-quality, code-simplification, security-and-hardening, performance-optimization
**Ship:** git-workflow-and-versioning, ci-cd-and-automation, deprecation-and-migration, documentation-and-adrs, observability-and-instrumentation, shipping-and-launch

## Conventions

- Every skill lives in `skills/<name>/SKILL.md`
- Every skill has a compact digest in `skills/<name>/COMPACT.md`
- YAML frontmatter with `name` and `description` fields
- Description starts with what the skill does (third person), followed by trigger conditions ("Use when...")
- Every skill has: Overview, When to Use, Process, Common Rationalizations, Red Flags, Verification
- References are in `references/`, not inside skill directories
- Supporting files only created when content exceeds 100 lines

## Context Optimization Protocol

**Goal**: Use <5% of context for skill guidance (vs 15-25% without optimization)

### Loading Modes
| Mode | When | What |
|------|------|------|
| **Compact** (default) | Session start, normal use | Load `compact/_all-compact.md` (~2,500 tokens) |
| **Full** | First time, complex task, error recovery | Load specific `skills/<name>/SKILL.md` |
| **Minimal** | Context critical (>80%) | Use inline from memory |

### Session Start
1. Load `compact/_all-compact.md` for all skill digests
2. Load project's `CLAUDE.md` (rules)
3. Check for handoff: `.handoff/*.md`

### Context Protection
Turn limits enforced automatically by `hooks/turn-guard.sh` (20/30/40 thresholds).
Use `/checkpoint` to save state before `/compact` or starting fresh.

### Creating Handoffs
Use `handoff/_template.md` for structure. See `handoff/_example.md` for reference.
Store handoffs in project's `.handoff/` directory, not here.

## Commands

- `npm test` — Not applicable (this is a documentation project)
- Validate: Check that all SKILL.md files have valid YAML frontmatter with name and description
- `/checkpoint` — Create session checkpoint before running /compact or starting new session

## Boundaries

- Always: Follow the skill-anatomy.md format for new skills
- Never: Add skills that are vague advice instead of actionable processes
- Never: Duplicate content between skills — reference other skills instead
