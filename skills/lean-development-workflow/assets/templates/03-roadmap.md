# <TICKET-ID> Roadmap

SPECS · Stage 3. The step plan, built from the scope + investigation. Test-first:
step 1 is always the failing test, written before implementation. Every step has
a concrete "done when"; every risk names the step that catches it.

**North Star:** <one sentence from the scope>
**Ticket:** <ID>

## Steps
| # | Step | File(s) | Done when | Status |
|---|------|---------|-----------|--------|
| 1 | Write the failing test | <test path> | <test command> → RED (expected fail) | next |
| 2 | Implement the smallest change (name the method) | <impl path> | <same test command> → GREEN | next |
| 3 | Run the relevant suite/checks | <module/dir> | no new failures | next |
| 4 | Independent code review (judge) | diff + tests | PASS, no blocking finding | next |
| 5 | Mutation check (meaningful changed logic) | <scope> | no meaningful survivor | next |

Status words: `next`, `in progress`, `done`, `blocked`, `partial`.

## Risks
| Risk | Caught by |
|------|-----------|
| <what could break> | <which step surfaces it> |
