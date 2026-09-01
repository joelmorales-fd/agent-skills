# <TICKET-ID>: <short title>

- **Stage:** <SPECS | TDD | JUDGE | MUTATION | BLOCKED | COMPLETE>
- **Owner:** <who approves the spec / resolves blockers>
- **Updated:** <date + time>

## Now
<One or two sentences: what the lead is doing this moment and why.>

## Last observed
<The real result of the last action — a command's exit + key output, a judge
finding, an answer from the owner. Facts, not interpretation.>

## Lead's read
<The lead's interpretation of that fact, including any uncertainty.>

## Next action
<The single next thing the lead will do automatically — no human needed.>

## Waiting on human
<Only when real: the one exact question or approval needed. Otherwise "none".>

## History
<Append-only, newest last. **Every** action adds one line here in the same write
that updates Now / Last observed — never skip it, never rewrite earlier lines.
One line per action, exactly: `YYYY-MM-DD HH:MM — STAGE — what happened` — time to
the minute (no seconds).>

## Completion report
<Filled only at COMPLETE — the durable delivery handoff, written here in the
ticket, never left only in the chat. This IS the report to the owner. Cover:
- **What changed** — the behavior, in the ticket's terms.
- **Key files** — as `path:line`.
- **Scope summary** — files approved (frozen `04-code-guide.md`) vs files shipped,
  and each `05-scope-changes.md` deviation. So the owner sees the final blast radius
  against what they approved.
- **Scenario coverage** — one row per `specification.md` scenario → the test (file +
  assertion) that exercises it → its GREEN evidence (command id / retVal). Every
  approved scenario appears; this is the proof the scenarios were actually used.
- **Verification** — each command run and its real result (exit/retVal).
- **Mutation evidence** — what was mutated and that the tests caught it.
- **Caveats** — anything that couldn't run, files to keep out of the commit, etc.>
