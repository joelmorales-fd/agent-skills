# <TICKET-ID>: <short title> — Test Plan

<Delete this paragraph when you write the file. Written only by the QA lead. It does not
change after the code review approves it.>

## 1. What changed

<The changed files and methods, read from their current code, and how each is reached
when the service runs, for example through an endpoint, a message consumer, or a
scheduled job. Name the file and line.>

## 2. Performance anti-pattern detection

### Findings

<Empty if there are none. One block per finding:>

#### Finding <n>: <short name>

- **File and line:** `<path>:<line>`
- **Pattern:** <which pattern, or a short description if it is not on the list>
- **Input that makes it grow:** <the input, and where it comes from: a request, the
  database, a message>
- **How the work grows:** <once per item, or once per item for every item>
- **How large the input can get:** <from the code or the specification, with where it
  says so>
- **Severity:** <critical | high | medium | low>
- **Why this severity:** <from how the work grows and how large the input can get>

### Notes

<Patterns whose input cannot grow, each with the file and line and the reason it is not
a finding. If there are none, write only "None." and nothing else.>

### No finding

<Only when there are no findings: what the changed code does, and why nothing in it
grows with the input, with the file and line.>

## 3. Test cases

None. Performance anti-pattern detection is found by reading the code, so nothing runs
against the service.

## 4. Where it runs

<The address of the deployed service, from the repository's `AGENTS.md` or from the
deployment, and where that came from.>
