# Investigation Reference — director2-aws

Grounding for the SPECS investigation so it is specific, not generic. The lead
hands this to the investigation specialist. (Other repos get their own reference
file next to this one; the method is the same.)

## Investigation method (all repos)

1. Start from the scope's "done when". Name the entry point the behavior flows through.
2. Open the real files; follow imports, callers, and usages outward.
3. Quote the exact block that changes with `File:line`.
4. Find and quote what already exists to reuse — reuse beats new code.
5. Trace the behavior end to end, including paths that must stay **unchanged**.
6. List open questions. No "probably / I think / likely / should be".

## Where things live (director2-aws)

- **Ops** are in `suite/<module>/src/` — the Op owning the behavior is usually the change.
- **Harness tests** are XML in `suite/<module>/test/` (`test-<operationName>.xml`).
  Indent with **spaces, not tabs** (a tab fails `git diff --check`).
- **Content search / Zoltar** ops live in `suite/media2/src/`.

## Domain rules to verify (and respect)

**Session identity & AVOD eligibility**
- `authUserId` may be **null** (anonymous) — null-check every path that uses it.
- Detect AVOD-anonymous via `AccountMapDef.isAvodAnonymousSession(authUserId)` —
  do **not** write a new check.
- Three session types handled **separately**: anonymous (null authUserId),
  authenticated non-AVOD, authenticated AVOD-eligible.
- **Non-AVOD behavior must be unchanged** — trace and prove that path.

**Redis**
- Every write sets an explicit **TTL**; no unbounded entries.
- Key naming follows the module's existing convention.
- After a session state change, stale entries are invalidated/ignored.
- Redis client is **not** created per-request (singleton/pooled).

**Content search (Zoltar)**
- Ranked by score; for AVOD sessions, AVOD-eligible titles promoted before others.
- **Do not modify scoring** — only the ordering of returned results.

## Reuse to check before writing new

- `AccountMapDef` and existing session utilities — most checks already exist.
- Existing fake-create ops / SQL fixtures for test setup.

## Harness execution (hand off to `director2-harness-test`)

Running the harness is the `director2-harness-test` skill's job. Two facts that
save time:
- `buildenv` needs a **pseudo-terminal**: `script -q /dev/null bash -ilc 'cd <root> && buildenv'`
  (plain `bash -ilc` fails no-TTY).
- Long commands (clean build, image rebuild, suite) run through the guard with
  `--out artifacts/<id>.json` so the result is durable even if stdout is dropped.
