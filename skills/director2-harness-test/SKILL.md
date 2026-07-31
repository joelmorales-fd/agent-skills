---
name: director2-harness-test
description: Runs director2-aws harness tests through the persistent build-container workflow. Use when you need to run one harness XML test, a whole director2 suite, or all director2 harness suites, and when you need to decide whether to rebuild director2 or rebuild the harness image before running the test.
---

# Director2 Harness Test

## Overview

Run a `director2-aws` harness test with the least setup needed, while preserving the persistent container flow that makes repeated local runs practical.

This skill exists for one repeated loop: make sure the build container is usable, rebuild only when necessary, run the requested harness target, and report whether the run passed or failed.
This skill is only for `director2-aws` harness execution.

## When to Use

- You need to run one `director2-aws` harness XML test
- You need to run a whole `director2-aws` suite such as `suite/dis`
- You need to run all harness suites with `.`
- You need to decide whether a harness failure is caused by stale build artifacts or stale harness image state
- `avod-ticket` has already decided the repo is `director2-aws` and needs the actual harness execution workflow

## When NOT to Use

- Running Gradle or Spring Boot test workflows for non-`director2-aws` repos
- Designing the harness test itself
- General benchmark triage after the harness run completes
- Broad Docker environment debugging unrelated to harness execution

Use `avod-ticket`, `benchmark-failure-triage`, or general debugging workflows for those.

## Required Inputs

- The harness target to run

Valid targets:

- One XML test path such as `suite/purchases/test/test-advertContents-noAdsAvailable.xml`
- One suite path such as `suite/dis`
- `.` for all suites

Helpful inputs:

- Whether Java code or schema files changed
- Whether the current harness image is known to be stale
- Whether the developer wants manual or automated buildenv steps
- How much Docker Desktop memory and CPU are available for choosing `-t`

## Command Shapes

Use `run-harness-sidecar.sh` from the host while the persistent build container stays running.

Common forms:

- single XML test: `./run-harness-sidecar.sh -p -t 1 -j 2048 /dis/test/test-foo.xml`
- single qualified XML test: `./run-harness-sidecar.sh -p -t 1 -j 2048 platform/test/test-foo.xml`
- one suite: `./run-harness-sidecar.sh -p -m -t 6 dis`
- all suites: `./run-harness-sidecar.sh -p -m -t 6 .`

Flag meanings:

- `-t N`: number of parallel harness threads and MySQL sidecars
- `-j N`: JVM heap for the harness Java process in MB
- `-p`: use `harness-mysql-preloaded:latest` and skip DB install
- `-m`: mount tmpfs for MySQL datadir; fastest option, usually paired with `-p`

Thread-count rule:

- choose `-t` based on available Docker Desktop resources, not just desired speed
- example: `-t 6` needs Docker memory 12 GB and CPU 7
- `-t 10` needs more Docker memory and CPU than that, so do not use it as a default
- use `-t 6` as the documented example unless the available Docker resources justify going higher
- if those resources are not available, lower `-t`
- when uncertain, start smaller rather than overcommitting Docker

## Process

### Step 1: Confirm the repo and target

Use this skill only inside a `director2-aws` checkout.

Confirm the requested target is one of:

- single test XML path
- suite path
- `.`

If the target is vague, narrow it before running anything.

### Step 2: Check the persistent build container

Check whether `director2-aws-build` already exists.

- If it is stopped, remove it
- If it is absent, create it
- If it is already running, reuse it

The container should stay alive across repeated test runs.

### Step 3: Check whether a rebuild is needed

Inspect local changes and decide whether to rebuild.

Rebuild when:

- Java code changed
- schema-related files changed
- the harness image is stale
- this is a first-time run and no trustworthy image exists

Skip rebuild when:

- the change is documentation-only
- you have a fresh image and only need another execution pass

### Step 4: Rebuild only if needed

If a rebuild is needed:

1. inside the persistent container, run `./gradlew clean build -PdisableRyuk` from the `director2/` directory to compile `director2`
2. if the pre-loaded image is stale or missing, rebuild it with `./build-harness-mysql-image.sh`

If no rebuild is needed, do not pay that cost.

### Step 5: Run the requested harness target

Run the target from the host with `./run-harness-sidecar.sh`.

Default choices:

- single XML test: `-p -t 1 -j 2048`
- suite runs: prefer `-p -m` and choose `-t` from Docker capacity

Do not call `./scripts/runDirHarness.py` directly unless you are debugging the harness scripts themselves.
Do not use debug mode unless explicitly asked.

Allowed target shapes:

- single XML test
- suite path
- `.`

### Step 6: Read the result

Capture:

- target run
- whether the run returned success
- any obvious failure signal
- where logs were written, if shown

### Step 7: End with the next move

If the run passed, the next move is usually `None`.

If the run failed, choose one smallest next move:

- rebuild and rerun
- inspect the failing logs
- narrow from suite to single test
- hand off to `benchmark-failure-triage`

## Output Format

Use this output every time:

```md
# Director2 Harness Test

## Target
[single test path | suite path | .]

## Container State
[reused | restarted | created]

## Rebuild Decision
[rebuilt director2 and harness image | reused existing image]

## Command Run
[exact harness command]

## Result
Passed | Failed | Needs rerun

## Evidence
- [key line from output]
- [log location or notable failure detail]

## Next Move
[one concrete next step, or "None"]
```

## Common Rationalizations

- "Always rebuild, it is safer"
- "Never rebuild, the old image is probably fine"
- "Run the full suite first even when one single failing XML test is enough"
- "A failed harness run automatically means the implementation is wrong"

## Red Flags

The workflow is drifting if:

- It runs outside `director2-aws`
- It rebuilds on every run without checking whether the image is stale
- It skips rebuild when Java or schema changes clearly require one
- It runs a broad suite when a single targeted test was requested
- It ends without a concrete next move after a failure

## Verification

- Confirm the target is explicit and valid
- Confirm the container state is reported
- Confirm the rebuild decision matches the local change state
- Confirm the output includes the command run, result, and one next move
