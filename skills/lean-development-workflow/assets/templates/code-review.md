# <TICKET-ID> Code Review

The judge's independent **code review** of the change (code + tests). One section
per pass, appended (never rewritten). The lead reads the verdict here and records
the resulting decision in `state.md`. The judge writes this file; the lead does not.

---

## Code Review <n> — <date> — stage JUDGE

**Reviewed:** <diff / tests the judge actually saw>
**Verdict:** <PASS | FAIL>

### Findings
<Empty if none. Each finding:>

- **[<critical|high|medium|low>] <blocking? yes/no>** — <location>
  - What: <the defect>
  - Why it matters: <impact on the approved scenario>
  - Fix: <what would resolve it>

### Prior findings checked (re-review only)
<For a re-review: list each earlier unresolved finding and whether it is now
resolved, with the evidence.>
