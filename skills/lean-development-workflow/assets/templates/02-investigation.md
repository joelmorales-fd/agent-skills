# <TICKET-ID> Investigation

SPECS · Stage 2. A specialist maps the current state of the code. Quote **real**
code with file paths and line numbers. No guesses — no "probably / I think /
likely / should be". The lead validates this against the scope before accepting.

**This is a shape to fill, not text to copy.** Delete every `<placeholder>`,
replace with real quoted code for THIS ticket, and do not paste the investigation
reference or its rules verbatim — apply them and show evidence from the real code.

**What the ticket is asking:** <one sentence — the North Star for what follows>

## Current behavior
For each file that will change, quote the relevant block and say what is wrong or
missing.

### <FileName>:<start>–<end>
```
<exact quoted code>
```
<One sentence: what is wrong or missing here.>

## What already exists to reuse
For each helper / pattern the implementation should use.

### <HelperName>:<line>
```
<exact quoted code>
```
Use this in <location> — do not write a new implementation.

## Where the change lives
| File | Lines | What changes |
|------|-------|--------------|
| <path> | <N–M> | <specific description> |
| <test path> | new / <N–M> | <new or modified test> |

## What is missing
<The specific code or test that does not yet exist, stated precisely.>

## Open questions
<Anything needing a decision before the roadmap. Block until resolved. If none,
write "None".>

## Domain rules applied
<Only the rules relevant to what THIS ticket actually touches, confirmed against
the real code with evidence. Draw them from the repo's investigation reference —
do not copy the whole list; include only what applies and cite the code that
proves it. If the ticket touches none, write "None relevant".>
