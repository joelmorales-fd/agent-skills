# <TICKET-ID>: <short title> — Scenario Acceptance

- **Stage:** <SCENARIOS | SCENARIO REVIEW | DEPLOY | VALIDATE | DECISION | BLOCKED | validated>
- **Ticket directory:** <path to the loop-1 ticket directory this runs against>
- **Updated:** <date + time>

## Now
<One or two sentences: what the lead is doing this moment and why.>

## Last observed
<The real result of the last action — changed YAML/diff, raw command output,
QA finding, or scenario-run result. Facts, not interpretation.>

## Lead's read
<The lead's interpretation of that fact, including any uncertainty. For an
unclear live failure, record the source-input → processing → materialization →
assertion evidence chain and its first broken boundary.>

## Next action
<The single next thing the Lead will do automatically, or the exact resume
condition for a genuine BLOCKED state.>

## Waiting on human
<Only when a genuine business/spec ambiguity requires loop-1 SPECS re-approval,
or an external execution prerequisite is unavailable. Engineering diagnosis,
runner limitations with existing exact harness proof, and routine routing never
wait on the owner. Otherwise "none".>

## Coverage ledger
<One row per approved behavior: LIVE → exact YAML assertion, or LOOP 1 HARNESS
→ exact test and direct GREEN evidence.>

## History
<Append-only, newest last. **Every** action adds one line here in the same
write that updates Now / Last observed — never skip it, never rewrite
earlier lines. One line per action, exactly:
`YYYY-MM-DD HH:MM — STAGE — what happened` — time to the minute (no
seconds). Name the artifact and real result the Lead judged — not merely the
employee's PASS/FAIL label.>

## Decision
<Filled only at DECISION — PASS/FAIL and what happened next:
- **PASS** — after the Lead verifies every required artifact, records its
  deliberate `validated` sign-off.
- **FAIL** — records the evidence and automatic route: loop-1 TDD for a code
  defect, loop-1 SPECS for an approved-contract defect, or Senior Engineer
  diagnosis when the cause is unclear.>
