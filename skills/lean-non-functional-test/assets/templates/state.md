# <TICKET-ID>: <short title> — Non-functional Test

- **Stage:** <DEPLOY | TEST PLAN | CODE REVIEW | RUN | DECISION | BLOCKED>
- **Code review round:** <0 until the first code review; +1 for each round>
- **Ticket directory:** <path to the Loop 1 ticket directory this runs against>
- **Loop 1 complete:** <the line from Loop 1's `state.md` that shows COMPLETE>
- **Updated:** <date + time>

## Now
<One or two sentences: what the Lead is doing this moment and why.>

## Last observed
<The real result of the last action: the file the Lead read and what it shows.
Facts, not interpretation.>

## Lead's read
<The Lead's interpretation of that fact, including any uncertainty.>

## Next action
<The single next thing the Lead will do, or the exact action a human must take for
BLOCKED.>

## Deploy
<Healthy or not, and the files in `test-output/` that hold the raw build and health
output.>

## History
<Append-only, newest last. One line per action, in the same write that updates Now and
Last observed:
`YYYY-MM-DD HH:MM — STAGE — what happened`. Use the machine's local time, the same
clock the watchdog log uses, and never write a time you did not observe. Name the file
the Lead read and what it showed, not an employee's label.>

## Decision
<Filled only at DECISION: PASS or FAIL, and the reason. The reason names each finding
and its severity that the decision rests on.>
