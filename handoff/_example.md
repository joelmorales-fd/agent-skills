# Example Handoff: User Authentication Feature

This is a **filled-in example** showing what a real handoff document looks like.

---

# Handoff: User Authentication

**Created**: 2024-01-15 16:45
**Session**: auth-feature-day1

---

## 1. Current State

### Active Workflow
- **Skill**: incremental-implementation
- **Phase**: IMPLEMENT, slice 3 of 5
- **Mode**: digest

### Current Task
```
Task: Task 3 - Login endpoint with JWT
Status: in-progress (70%)
Progress: 
  ✓ POST /api/auth/login route created
  ✓ Credential validation logic
  ✓ JWT token generation
  ○ Session cookie setup (next)
  ○ Response formatting
Next step: Add httpOnly cookie with JWT in login response (auth.routes.ts:45)
```

### Files Modified This Session
| File | Status | Change |
|------|--------|--------|
| `src/routes/auth.ts` | Created | Register + login endpoints |
| `src/services/auth.service.ts` | Created | Validation, hashing, JWT |
| `src/lib/jwt.ts` | Created | Sign/verify utilities |
| `src/types/auth.ts` | Created | User, Token interfaces |
| `tests/routes/auth.test.ts` | Created | 8 tests (6 pass, 2 pending) |
| `prisma/schema.prisma` | Modified | Added User model |

### Uncommitted Changes
```bash
# Verified at 16:40:
# 6 files changed, 342 insertions
# All changes staged, not yet committed
# Waiting for Task 3 completion before commit
```

---

## 2. Decisions Made

| # | Decision | Rationale | Rejected Alternative |
|---|----------|-----------|---------------------|
| 1 | JWT for auth tokens | API-first design, stateless scaling | Sessions: need Redis |
| 2 | bcrypt with 12 rounds | OWASP minimum, 250ms hash time | 10 rounds: too fast |
| 3 | 15-min access token | Balance security/UX | 1-hour: too long |
| 4 | 7-day refresh token | Mobile needs long sessions | 24-hour: friction |
| 5 | Cookies over localStorage | XSS protection (httpOnly) | localStorage: XSS risk |
| 6 | Zod for validation | Already in codebase | Joi: another dep |

---

## 3. Context & Constraints

### Confirmed Constraints (from spec)
- Must support email/password auth (no social login in MVP)
- Must work with existing Prisma/PostgreSQL setup
- API responses follow existing error format
- No breaking changes to existing endpoints

### Assumptions (not yet validated)
- Email uniqueness enforced at DB level — **To validate**: Check migration
- Frontend will handle token refresh — **To validate**: Confirm with spec
- Rate limiting handled by API gateway — **To validate**: Check infra

### Known Issues / Tech Debt
- TODO: Add rate limiting to login endpoint
- TODO: Password reset flow (separate task)
- Note: `jwt.ts` could use env validation for secrets

---

## 4. Remaining Work

### This Feature
- [ ] **Task 3 (current)**: Complete login endpoint — Accept: JWT in httpOnly cookie
- [ ] **Task 4**: Logout endpoint — Accept: Clears auth cookie
- [ ] **Task 5**: Auth middleware — Accept: Protects routes, extracts user
- [ ] **Review checkpoint**: Self-review, then code review

### Blocked Items
| Item | Blocked By | Unblock Action |
|------|------------|----------------|
| Refresh token rotation | Need storage decision | Ask: Redis vs DB? |

---

## 5. Technical Reference

### Patterns Established
```typescript
// Pattern: Route handler structure
// Used for: All auth routes
router.post('/register', async (req, res) => {
  try {
    const validated = RegisterSchema.parse(req.body);
    const result = await authService.register(validated);
    return res.status(201).json(result);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return res.status(400).json({
        error: { code: 'VALIDATION_ERROR', message: error.errors[0].message }
      });
    }
    throw error;
  }
});
```

```typescript
// Pattern: Service method structure
// Used for: All auth service methods
async register(input: RegisterInput): Promise<AuthResponse> {
  // 1. Validate business rules
  const existing = await db.user.findUnique({ where: { email: input.email } });
  if (existing) {
    throw new AuthError('EMAIL_EXISTS', 'Email already registered');
  }
  
  // 2. Perform operation
  const hashedPassword = await hash(input.password, 12);
  const user = await db.user.create({ ... });
  
  // 3. Return result (never include password)
  return { user: { id: user.id, email: user.email } };
}
```

### Key Files
- `src/routes/auth.ts` — All auth endpoints
- `src/services/auth.service.ts` — Business logic
- `src/lib/jwt.ts` — Token utilities
- `tests/routes/auth.test.ts` — Integration tests

### Commands
```bash
# Verify current state
npm test -- --grep "auth"

# Run all tests
npm test

# Type check
npx tsc --noEmit

# Start dev server
npm run dev
```

---

## 6. Resume Instructions

### Before Coding
1. Read this entire handoff
2. Run: `npm test -- --grep "auth"` → Should see 6 pass, 2 pending
3. Run: `git status` → Should see 6 modified files
4. Open: `src/routes/auth.ts:45` → Continue from here

### Load Context
1. Load `compact/_all-compact.md` for skill reference
2. Active skill: **incremental-implementation** in **IMPLEMENT** phase
3. Review decisions — especially #5 (cookies) for current task

### Continue From
**Exact next step**: Add httpOnly cookie to login response

**Code to add** (at line 45):
```typescript
res.cookie('auth_token', token, {
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax',
  maxAge: 15 * 60 * 1000, // 15 minutes
});
```

**After that**: 
1. Update response to not include token in body
2. Write test for cookie presence
3. Mark Task 3 complete
4. Commit: "feat(auth): add login endpoint with JWT cookie"

---

## 7. Compact Skill Reference

### incremental-implementation

**Process (The Cycle)**
1. **IMPLEMENT**: Smallest complete piece
2. **TEST**: Run test suite
3. **VERIFY**: Tests pass, build clean
4. **COMMIT**: Descriptive message
5. **NEXT**: Repeat for next slice

**Hard Rules**
- One thing at a time
- Keep it compilable
- Simplicity first
- Scope discipline: Touch ONLY what task requires

**Gate**: Each slice: tests pass AND build succeeds

---

## Verification Checklist (For New Session)

After loading this handoff, confirm:
- [ ] Ran `npm test -- --grep "auth"` — see 6 pass, 2 pending
- [ ] Understand: Add cookie to login response
- [ ] Know cookie settings (httpOnly, secure, sameSite, maxAge)
- [ ] Won't re-debate JWT vs sessions (decided)
- [ ] Won't add social login (out of scope)
