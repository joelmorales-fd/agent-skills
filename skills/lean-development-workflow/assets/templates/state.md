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
One line per action: date — stage — what happened.>

## Completion report
<Filled only at COMPLETE — the durable delivery handoff, written here in the
ticket, never left only in the chat. This IS the report to the owner. Cover:
- **What changed** — the behavior, in the ticket's terms.
- **Key files** — as `path:line`.
- **Verification** — each command run and its real result (exit/retVal).
- **Mutation evidence** — what was mutated and that the tests caught it.
- **Caveats** — anything that couldn't run, files to keep out of the commit, etc.>
