---
name: git-workflow-and-versioning
mode: compact
---

# git-workflow-and-versioning — Compact

## Trigger
- Making commits
- Creating or managing branches
- Preparing pull requests

## Commit Rules

**Atomic Commits**: One logical change per commit
```bash
# Good: Separate commits
git commit -m "Add user validation schema"
git commit -m "Add user registration endpoint"

# Bad: Mixed concerns
git commit -m "Add validation, registration, and fix typo"
```

**Message Format**: Imperative mood, <72 characters
```
✅ "Add user registration endpoint"
✅ "Fix null pointer in auth middleware"
❌ "Added registration"
❌ "Fixing the bug"
```

**Conventional Commits** (optional):
```
feat(auth): add password reset flow
fix(api): handle null user in profile endpoint
docs: update API documentation
test: add integration tests for checkout
refactor(db): extract query builder
```

## Branch Strategy
```
main ─────────────────────────────────────────→
  │                                      ↑
  └── feature/user-auth ────────────────→ (merge)
  │                                      ↑
  └── fix/login-validation ─────────────→ (merge)
```

- `main` — Production-ready, always deployable
- `feature/[name]` — New features
- `fix/[name]` — Bug fixes
- `hotfix/[name]` — Urgent production fixes

## Hard Rules
- ❌ **Never commit secrets** (API keys, passwords, tokens)
- ❌ **Never force-push shared branches** (`main`, `develop`)
- ✅ **Tests pass before push**
- ✅ **Pull/rebase before push** to avoid conflicts

## PR Checklist
```markdown
- [ ] Tests pass locally
- [ ] Build succeeds
- [ ] Self-reviewed the diff
- [ ] Linked to issue/task
- [ ] No console.log or debug code
- [ ] No secrets in code
```

## Quick Commands
```bash
# Start feature
git checkout -b feature/my-feature

# Keep up to date
git fetch origin
git rebase origin/main

# Squash commits before PR
git rebase -i HEAD~3

# Undo last commit (keep changes)
git reset --soft HEAD~1
```

---

→ **Full guidance**: `skills/git-workflow-and-versioning/SKILL.md`
