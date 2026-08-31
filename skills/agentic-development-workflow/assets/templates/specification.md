<!-- ADW-TEMPLATE: synthesize the completed package and Gherkin, then remove this marker -->
# Specification: [Ticket ID — Title]

## Ticket and Goal

- Ticket: [ID/link]
- Goal: [What changes and why]
- Done when: [Observable result]
- Owner approval: [Name and date]
- Approved specification revision ID: [SPEC-revision]
- Approved specification snapshot/fingerprint: [safe artifact/integrity reference]
- Specification approval evidence ID: [E-APPROVAL-ID]

## Scope and Constraints

- Approved scope source: [01-scope.md](01-scope.md)
- In scope: [Items]
- Out of scope: [Items]
- Constraints: [Compatibility, modules, environment, or other limits]

## Specification Package

- [Scope](01-scope.md)
- [Repository investigation](02-investigation.md)
- [Roadmap](03-roadmap.md)
- [Code guide and preliminary test plan](04-code-guide.md)

## Configuration Resolution Record

- Repository/workspace/branch: [context]
- Repository QA test profile and validation reference: [link/revision]
- Verified local QA capabilities: [runner/harness/test paths/lifecycle constraints]
- Feature-specific configuration to investigate in TEST_DESIGN: [applications, databases, dependencies, commands, readiness]
- Prohibited assumptions / unavailable paths: [items]
- Next investigation owner and action: [items]

## Acceptance Criteria

- [Observable normal behavior]
- [Observable negative/error behavior]
- [Boundary or regression invariant]

## Gherkin Scenarios

```gherkin
Scenario: [Name]
  Given [setup]
  When [action]
  Then [observable result]
```

## Approval Record

Append one approval record per specification revision. Never rewrite a prior approval to make it appear to cover changed behavior.

- Approver: [developer/ticket owner]
- Producer reference and runtime-issued proof: [safe human account/approval record ID / proof]
- Approval time: [time]
- Approved scope/Gherkin revision: [revision]
- Approval evidence ID and integrity reference: [E-ID / reference]
- Approved constraints or exceptions: [none/items]

Detailed Scenario Verification Contracts are created after owner approval in `TEST_DESIGN`; they cannot silently change this approved behavior contract.
