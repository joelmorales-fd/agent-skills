# <TICKET-ID> Scenario Acceptance Verdict

The QA lead's independent verdict on whether the deployed change satisfies
`specification.md`'s scenarios. One section per pass, appended (never
rewritten). The lead reads the verdict here and records the resulting
DECISION in `scenario-acceptance-state.md`. The QA lead writes this file;
the lead does not.

---

## Verdict <n> — <date> — stage VALIDATE

**Fed:** <frozen `specification.md` + the scenario YAML path(s) + raw runner
output the QA lead actually read — report.html / JUnit path, never a
narrative from the Engineer or SRE>
**Verdict:** <PASS | FAIL>

### Coverage check
<One row per `specification.md` Given/When/Then — does a scenario assert it,
and is that assertion specific enough that it could not pass with the wrong
result? Cite the exact assertion.>

| Scenario behavior | Asserted by | Specific? | Note |
|---|---|---|---|
| <Given/When/Then> | <scenario file:step> | <yes/no> | <why, if not tight> |

### Findings
<Empty if none. Each finding:>

- **[<critical|high|medium|low>] <blocking? yes/no>** — <location>
  - What: <the defect — a loose assertion that could pass with the wrong
    result, a real behavior failure, an environmental issue>
  - Why it matters: <impact on the approved scenario/spec>
  - Evidence: <report path, exit code, or specific failing row/response>
  - Fix: <what would resolve it>

### Prior findings checked (re-review only)
<For a re-review: list each earlier unresolved finding and whether it is now
resolved, with the evidence.>
