---
name: security-and-hardening
mode: compact
---

# security-and-hardening — Compact

## Trigger
- Building anything that accepts user input
- Implementing authentication or authorization
- Storing or transmitting sensitive data
- Integrating with external APIs
- Adding file uploads, webhooks, or callbacks

## Always Do (No Exceptions)
- ✅ **Validate all external input** at system boundaries
- ✅ **Parameterize all database queries** (never concatenate)
- ✅ **Encode output** to prevent XSS (use framework auto-escaping)
- ✅ **Use HTTPS** for all external communication
- ✅ **Hash passwords** with bcrypt ≥12 rounds (never plaintext)
- ✅ **Set security cookies**: `httpOnly`, `secure`, `sameSite: 'lax'`
- ✅ **Run `npm audit`** before every release

## Never Do
- ❌ **Commit secrets** to version control
- ❌ **Log sensitive data** (passwords, tokens, full CC numbers)
- ❌ **Trust client-side validation** as security boundary
- ❌ **Use `eval()` or `innerHTML`** with user data
- ❌ **Store auth tokens in localStorage** (use httpOnly cookies)
- ❌ **Expose stack traces** to users in production

## Ask First (Requires Human Approval)
- New authentication flows or auth logic changes
- Storing new categories of sensitive data (PII, payment)
- Adding new external service integrations
- Changing CORS configuration
- Adding file upload handlers
- Modifying rate limiting

## Quick Patterns

**Input Validation (Zod)**:
```typescript
const schema = z.object({
  email: z.string().email().max(255),
  password: z.string().min(8).max(128),
});
const validated = schema.parse(req.body);
```

**Parameterized Query**:
```typescript
// GOOD
const user = await db.query('SELECT * FROM users WHERE id = $1', [userId]);
// BAD - SQL injection
const user = await db.query(`SELECT * FROM users WHERE id = '${userId}'`);
```

**Password Hashing**:
```typescript
const hash = await bcrypt.hash(password, 12);
const valid = await bcrypt.compare(password, hash);
```

---

→ **Full guidance**: `skills/security-and-hardening/SKILL.md`
→ **Checklist**: `references/security-checklist.md`
