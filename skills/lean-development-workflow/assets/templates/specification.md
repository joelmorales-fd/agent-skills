# <TICKET-ID> Specification

## Behavior
<What the change must do, in plain language. Grounded in the real code —
reference actual files/functions, not a summary.>

## Existing work & RED strategy
<What implementation/tests already exist. How the first test will fail honestly
(RED) without faking it: add a new test, or a real current failure.>

## Scenarios (Gherkin)
<The feature contract. Each scenario is the source of a test.>

```gherkin
Feature: <feature>

  Scenario: <name>
    Given <precondition>
    When <action>
    Then <observable result>
```

## Out of scope
<What this ticket deliberately does not change.>

---
Approved by: <owner>   Date: <date>
