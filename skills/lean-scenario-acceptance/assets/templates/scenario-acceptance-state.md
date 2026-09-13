# <TICKET-ID>: <short title> — Scenario Acceptance

- **Stage:** <SCENARIOS | DEPLOY | VALIDATE | DECISION | BLOCKED | validated>
- **Ticket directory:** <path to the loop-1 ticket directory this runs against>
- **Updated:** <date + time>

## Now
<One or two sentences: what the lead is doing this moment and why.>

## Last observed
<The real result of the last action — a deploy skill's exit code + report
path, a QA lead finding, a scenario-run result. Facts, not interpretation.>

## Lead's read
<The lead's interpretation of that fact, including any uncertainty.>

## Next action
<The single next thing the lead will do automatically — no human needed.>

## Waiting on human
<Only when real: the one exact question or approval needed (e.g. a BLOCKED
env dependency, or a FAIL parked for triage). Otherwise "none".>

## History
<Append-only, newest last. **Every** action adds one line here in the same
write that updates Now / Last observed — never skip it, never rewrite
earlier lines. One line per action, exactly:
`YYYY-MM-DD HH:MM — STAGE — what happened` — time to the minute (no
seconds). When a result came from `docker-director2-deploy`, the line names
the real exit code and report path — not just "ran scenarios".>

## Decision
<Filled only at DECISION — PASS/FAIL and what happened next:
- **PASS** — validated; loop 2 done for this ticket.
- **FAIL** — parked for human triage (fail routing to a specific loop-1
  stage is not yet resolved — see the skill's Non-negotiables). Name the
  exact evidence (report path, failing assertion) the human triages against.>
