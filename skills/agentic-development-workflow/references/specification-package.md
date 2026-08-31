# AVOD-Style Specification Package

Use this contract only while the work item is in `SPECIFY`. The package is complete only when all five documents below contain ticket-specific, repository-grounded content.

## Required Output

```text
<ticket-directory>/
  <optional-original-ticket-source>
  01-scope.md
  02-investigation.md
  03-roadmap.md
  04-code-guide.md
  specification.md
```

Additional investigation documents may be added when later research uncovers a material question. Keep them in the same ticket directory and reference them from the roadmap, evidence, review, or completion record.

The ticket is a source, not a required filename or format. It may come from Jira, another external system, a pasted request, or one local/exported file. Record a stable external reference when one exists. When a local source exists, preserve its original safe filename and bytes; do not force `.txt`, `.md`, or a rename step. The five generated workflow documents above remain Markdown because they are the human-readable approval package.

## Intake and Research Sequence

1. Resolve and read the ticket source without changing it. Record its source system/reference and preserve any local source artifact under its original name.
2. Establish repository, change type, observable done condition, constraints, prior context, and explicit exclusions.
3. Inspect fresh repository status and the ticket-relevant diff. Record whether implementation or tests already exist and select the safe RED strategy before approval.
4. Ask one useful question when the ticket cannot answer a material point.
5. Inspect the actual repository. Follow callers, imports, queries, data/event flow, existing tests, fixtures, and repository-supported commands until the behavior is traced end to end.
6. When research exposes a new uncertainty, ask or investigate again. Do not collapse this loop into a guessed conclusion.
7. Write the investigation using quoted repository code with current file paths and line numbers.
8. Derive the roadmap, code guide, acceptance criteria, and Gherkin from the verified investigation.
9. Run `record-specification`. Request human approval only after it succeeds.

## `01-scope.md`

Record:

- ticket identifier and title;
- repository and change type;
- one-sentence goal;
- externally observable done condition;
- constraints and compatibility requirements;
- prior context;
- explicit out-of-scope behavior.
- fresh baseline evidence identifying any ticket implementation or tests already present;
- one safe RED strategy: `normal-red-first`, `current-failing-test`, `isolated-clean-baseline`, or `blocked`.

`normal-red-first` is valid only when no ticket implementation or tests exist at intake. If work is already present, use a currently failing approved test, an explicitly configured isolated clean baseline, or `blocked`. Never manufacture historical RED by reversing, stashing, resetting, or restoring the active worktree.

Do not begin repository investigation until the ticket scope is understood. If the owner must resolve a material ambiguity, ask before presenting the package as ready.

## `02-investigation.md`

This is the durable repository investigation—not a prose summary. It must contain:

- the ticket's North Star;
- current behavior traced through the real code/data/event path;
- exact quoted code blocks under `path:line-line` headings;
- existing helpers, queries, fixtures, or tests to reuse, also quoted;
- a table of files, current lines, and exact expected change;
- a precise statement of what is missing;
- open questions, or `None`;
- any supported command or topology facts needed to make the later test design credible.

Every referenced method or file must have been read. Do not use `probably`, `I think`, `likely`, or `should be` for code facts. If a fact cannot be verified, label it unknown and continue the investigation loop.

## `03-roadmap.md`

Create a living plan derived from the investigation. Every row names files, a concrete action, a verifiable done condition, and a status. It must include:

1. a RED test or scenario using the repository-supported boundary;
2. the smallest implementation that makes the same proof GREEN;
3. the affected full-suite check;
4. independent code review;
5. local verification and evidence-backed completion.

Name which step catches every documented risk. Later agents update statuses as evidence is recorded; they do not replace the roadmap with a new undocumented plan.

## `04-code-guide.md`

Record:

- exact files and locations to change;
- the verified existing pattern to follow, with a file/line reference;
- files or behavior that must not change;
- configuration impact, or `None`;
- the preliminary test plan with concrete setup, action, observable result, and boundary cases.

This guide narrows implementation. It does not authorize coding; `TEST_DESIGN` must still prove every approved Gherkin scenario is executable and trustworthy.

## `specification.md`

Synthesize the approval contract and link the other four documents. Include:

- ticket and goal;
- scope and constraints;
- links to the scope, investigation, roadmap, and code guide;
- observable acceptance criteria;
- Gherkin scenarios with `Given`, `When`, and `Then`;
- the approval record.

Do not duplicate the investigation as a few bullets. The linked investigation is part of the exact package being approved.

## Mechanical Gate

Run:

```bash
python3 <absolute-skill-path>/scripts/adw.py record-specification <ticket-id> \
  --delivery-root <configured-root> \
  --reason <safe-reason> --request-id <unique-request-id> \
  --expected-sequence <n> --expected-head <sha256:...> \
  --lead-run-ref <safe-lead-reference> --format json
```

The command rejects missing templates, an unsafe or inconsistent RED strategy, shallow investigation structure, unverified hedge language, a roadmap without RED/GREEN/full-suite/review steps, a code guide without a verified pattern and test plan, or a specification without linked package documents and Gherkin. On success it atomically creates one immutable human-readable package snapshot and records the new `specification` revision.

The generic `record-revision --domain specification` path is forbidden so the package gate cannot be bypassed.

## Returning After Later Investigation

An approved package is not permanent when later investigation proves it materially wrong or incomplete. If the workflow is already in `TEST_DESIGN` or a later state, first use `route-correction --target-state SPECIFY` with a concrete reason and next action. That atomic correction preserves the history, invalidates the old approval and downstream gates, and makes `SPECIFY` authoritative again. Then update the five package documents, run `record-specification`, and request approval for the new immutable revision. A plain approval reply cannot substitute for the correction transition or approve unrecorded working documents.

## Human Approval

Before preflight, the active write declaration must already list the exact ticket documents and implementation/test files justified by the code guide. Run `prepare-approval` alone in one tool call with the fresh audit sequence/head before asking the responsible developer or ticket owner. Preflight binds that declaration to the workflow, ticket, immutable revision, and approval request and sets it unapproved. If preflight succeeds, ask them to review the immutable snapshot returned by `record-specification` and reply `I approve`. For this workflow only, that reply captures the human approval and authorizes the matching bound declaration; no second `proceed` is required, and no new or unrelated files are authorized. Then read fresh status and run `record-approval` alone to record approval atomically without a proposal file. If a fresh host receipt is missing, rerun the relevant command alone; only restart when a separate call still shows that hooks are unavailable. If any package document changes materially, run `record-specification` and preflight again for the new revision. An approval prepared for an older revision cannot authorize it.
