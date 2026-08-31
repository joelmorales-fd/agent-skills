<!-- ADW-TEMPLATE: ground the guide in the investigation and preliminary test plan, then remove this marker -->
# Code Change Guide + Test Plan: [Ticket ID — Title]

## Files to change

| File | What changes |
|---|---|
| `path/to/file` | [Exact method/query/configuration change] |

## Pattern to follow

Follow `path/to/verified-pattern.ext:1` — [why this is the correct existing pattern].

## What NOT to change

[Related files, behavior, or interfaces outside this ticket]

## Config changes

[Exact configuration impact, or `None`]

## Test Plan

| Case | Setup | Action | Expected result |
|---|---|---|---|
| [Normal scenario] | [Supported setup] | [Real boundary action] | [Observable result] |
| [Negative scenario] | [Supported setup] | [Real boundary action] | [Observable absence/error] |
| [Boundary/regression] | [Supported setup] | [Real boundary action] | [Invariant] |
