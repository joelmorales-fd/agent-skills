---
name: director2-harness-test
description: Runs director2-aws harness tests through the required persistent-container clean build and preloaded-image workflow. Use when you need to run one harness XML test, a whole director2-aws suite, or all director2-aws harness suites.
---

# Director2 Harness Test

## Overview

Run a `director2-aws` harness test through the required clean-build and preloaded-image setup while preserving the persistent container flow.

This skill exists for one repeated loop: make sure the build container is usable, clean-build Director2, recreate the preloaded harness image, run the requested target, and report whether the run passed or failed.
This skill is only for `director2-aws` harness execution.

## When to Use

- You need to run one `director2-aws` harness XML test
- You need to run a whole `director2-aws` suite such as `suite/dis`
- You need to run all harness suites with `.`
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

## Configuration Resolution

Resolve the local capability in this order and stop at the first validated option:

1. If `director2-aws-build` exists and is running, reuse it only when it uses the configured local server-build Docker image and mounts the intended `director2-aws` checkout at `/director2-aws`.
2. If the container does not exist, from the host `director2-aws` checkout invoke the configured `buildenv` alias with no leading `.` or `./` and no image argument. On the configured local machine, `buildenv` is a Bash login alias from `~/.bash_profile`; validate it with `bash -ilc 'type buildenv'`, then invoke it with `bash -ilc 'cd <director2-aws-root> && buildenv'`. A zsh lookup does not test this Bash alias and must not be reported as a blocker.
3. If the alias cannot be loaded from the configured profile, or the container exists but is stopped or invalid, stop with the exact blocker. Do not invoke the alias target script directly, remove or replace the container, or invent another container path.

These are three separate resources:

- **Server-build Docker image:** must already exist locally. This workflow never builds, pulls, publishes, or replaces it.
- **`director2-aws-build` container:** if absent, create it only through the `buildenv` alias. The machine's buildenv configuration selects the existing server-build image; the caller does not pass an image reference. Never invoke the target script directly or create the container with `docker run`.
- **`harness-mysql-preloaded:latest` image:** after the Director2 clean build succeeds, always recreate it from the host `director2/` directory with `./build-harness-mysql-image.sh`. This local builder creates the native ARM64 image required by the Apple Silicon sidecar runner.

Before a run, validate Docker capacity, the selected image, the container mount, and `/director2-aws/director2` inside the container. The documented `-t 6` suite example requires at least 12 GB Docker memory and 7 CPUs; reduce concurrency when the validated capacity is lower.

Before starting the clean build, use a bounded request from inside the build container to confirm `nexus3.mgo.com` is reachable. The harness-image builder requires its dbschema metadata; if Nexus is unavailable, report the VPN/network blocker instead of compiling or reusing an old harness image.

Compile from `/director2-aws/director2` with `./gradlew clean build -PdisableRyuk`, always recreate the harness image, and then run the sidecar command from the host checkout. Monitor `main.log`, every `harness_*.log`, and sidecar state until a terminal result or configured no-progress timeout; repeated bootstrap lines alone are not proof that work is advancing.

Record the selected non-secret option, validation results, exact commands, and resulting logs in the ticket-local configuration revision and evidence. Never store machine configuration in the documentation repository and never hand-edit workflow-owned `.adw` files.

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

- If it is already running and its image/mount validate, reuse it
- If it is absent, invoke the configured Bash login `buildenv` alias from the host checkout
- If it exists but is stopped or invalid, stop with the exact blocker
- Never remove or create this container directly

The container should stay alive across repeated test runs.

Before continuing, confirm Nexus is reachable from inside the container with a bounded timeout. Stop with the VPN/network blocker when it is not.

### Step 3: Clean-build Director2

Inside the persistent container, always run `./gradlew clean build -PdisableRyuk` from the `director2/` directory.

### Step 4: Recreate the harness image

After the clean build succeeds, always run `./build-harness-mysql-image.sh` from the host `director2/` directory to create the native ARM64 `harness-mysql-preloaded:latest` image.

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
[reused | created]

## Build Preparation
[clean build result and harness image creation result]

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

- "The prior clean build is recent enough"
- "Recreate the preloaded harness image only after a harness failure"
- "Run the full suite first even when one single failing XML test is enough"
- "A failed harness run automatically means the implementation is wrong"

## Red Flags

The workflow is drifting if:

- It runs outside `director2-aws`
- It skips `./gradlew clean build -PdisableRyuk`
- It invokes a buildenv script path instead of the `buildenv` alias
- It treats a missing zsh alias as evidence that the configured Bash login alias is unavailable
- `harness-mysql-preloaded:latest` was not recreated for the current run
- It runs a broad suite when a single targeted test was requested
- It ends without a concrete next move after a failure

## Verification

- Confirm the target is explicit and valid
- Confirm the container state is reported
- Confirm the clean build passed and the harness image was recreated
- Confirm the output includes the command run, result, and one next move
