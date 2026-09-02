# Scope Changes — <TICKET-ID>

Deviations from the **frozen** `04-code-guide.md`, recorded during TDD. The guide
is never edited; every scope change lands here instead, so the growth is visible
and the judge can check it against what the owner approved.

A **contract** change does **not** belong here — it routes back to SPECS for owner
re-approval. Only accepted **internal** misses are recorded below.

| File | Change | Why (vs frozen guide + original ticket) | Kind |
|---|---|---|---|
| `path/File.ext` | <what changed> | <why the guide missed it / the approved behavior needs it> | internal |

## Rules

- **Kind is `internal` only.** A schema/API/signature/wire-payload/new-behavior
  change is a **contract** change → stop, back to SPECS. It is not recorded here as
  accepted.
- **NOT for any change to what a test asserts as correct output** (editing an
  existing assertion's expected values, or adding rows to it). Redefining "correct"
  is a behavior decision → back to SPECS, never an internal miss recorded here.
- **No percentage threshold** — judged by kind, not size. A one-line schema field is
  still a contract change.
- **Watch the cascade.** A third entry usually means the approach is wrong — stop and
  reconsider it (a Senior Engineer if needed), don't keep adding rows.
