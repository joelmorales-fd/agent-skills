# <TICKET-ID> Code Guide + Test Plan

SPECS · Stage 4. Exact instructions for what to change and what tests to write.
Feeds TDD directly.

## Files to change
| File | What changes |
|------|--------------|
| <path> | <exact description — e.g. "add null check on X before calling Y at line N"> |
| <test path> | <new test cases — see test plan below> |

## Pattern to follow
<Reference the specific existing file/method from the investigation and quote it.
"Follow <Helper>.<method>() at line N — use this exact helper, do not write a new
one.">

## What NOT to change
<Files that look related but must not be touched — prevents scope creep.>

## Config changes
<Any config key to add/change and which environment to deploy first — or "None
required".>

## Test plan
Written before any code. Be specific about inputs and expected outputs.

| Case | Setup | Input | Expected | Level |
|------|-------|-------|----------|-------|
| happy-path-<scenario> | <state/fixtures> | <input values> | <response/fields> | <harness / @SpringBootTest / unit> |
| error-<missing-field> | <minimal> | <invalid input> | <error response> | <level> |
| edge-<boundary> | <state> | <boundary value> | <behavior> | <level> |

Notes:
- <fixtures / TestContainers / fake-create ops needed>
- <cleanup or rollback required?>
- <no hardcoded IDs, tokens, or production data>
