---
name: docker-director2-deploy
description: Deploys a completed director2-aws change into the shared docker-director2 lower env and confirms it's healthy. Use when you need to get a branch's built image running in docker-director2 — it does not author or run acceptance scenarios.
---

# Docker Director2 Deploy

## Overview

This skill exists for one repeated loop: configure docker-director2 for the
change under test, bring the shared lower env up, and confirm it's healthy.
**Three sequential mechanical steps** — write a config file, then call the
same scripts directly. It manages the deployment environment only; it
takes an already-built image as given and never builds one itself.

## When to Use

- You need to deploy a branch-built director2-aws (or CIS/portal/ncis/
  webclient/dmedia) image into the shared docker-director2 lower env
- You need to bring the docker-director2 suite up/confirm it's healthy for a
  ticket already deployed
- `lean-scenario-acceptance`'s DEPLOY stage needs the actual deploy execution

## When NOT to Use

- Authoring the acceptance scenarios themselves — that's the Engineer's job
  in `lean-scenario-acceptance` (reads the frozen spec package + the real
  code diff, writes the scenario YAML)
- Running the scenarios or rendering a PASS/FAIL verdict — that's the QA
  lead's job; the QA lead invokes `scenarios/run_scenarios.sh` directly
  against the env this skill stood up, once this skill reports healthy
- Deciding stages, roles, or ticket-directory files — that's
  `lean-scenario-acceptance`'s job; this skill has no concept of a ticket

## Required Inputs

The caller (`lean-scenario-acceptance`) resolves all of these before invoking
this skill — this skill takes them as given, it never derives them itself:

- **Which service changed**. `CIS`, `router`, `data1`, `data2`, `avod1`,
  `promocode`, `ls`, `hadoop` all share `DIRECTOR_DEPLOY_VERSION`.
- **`DB_DEPLOY_TYPE`** — `AWS`, or a CSV of specific service DBs to run
  locally (e.g. `router,data1,data2`). How the caller derives this from the
  scenario is out of scope here — see `lean-scenario-acceptance`'s DEPLOY
  stage.

## Process

Run from `docker-director2/configurations/`.

### Step 1: CONFIG — write `environments.env`

Run this skill's own `set-config.py` (it lives in this skill's `scripts/`
directory, not in the `docker-director2` checkout) from
`docker-director2/configurations/`, so it finds `environments.env` there:

```
python3 <path-to-this-skill>/scripts/set-config.py --director-version local|latest \
  --services <CSV of services the scenario needs> \
  --db-deploy-type <AWS, or CSV of specific service DBs>
```

- `--director-version` → `local` for the changed service's deploy, `latest`
  otherwise.
- `--services` → the scenario's needed services; `kafka,redis` are appended
  automatically.
- `--db-deploy-type` → the value the caller passed in (`AWS`, or a CSV of
  specific service DBs).
- `UPDATE_DATABASES=No` is written automatically — never a flag.

### Step 2: UP — bring the env up

Run `./local-up.sh` from `configurations/`.

- Hard-fails immediately if the GlobalProtect VPN isn't up
  (`local-up.sh:36-40`) — this is a real, transient infra dependency, not a
  design flaw. Report the VPN blocker plainly; don't work around it.
- Per non-kafka service in `DEPLOY_TYPE`, resolves its tag via
  `getBaseContainerTag.sh`/`getDockerRepo.sh` and runs
  `docker-compose build --no-cache`, which picks up the locally-tagged image
  for any service set to `local`.
- `DB_DEPLOY_TYPE=AWS` (case-insensitive, plus the legacy `A,W,S`) skips
  local DB compose entirely (`local-up.sh:124-135`).

### Step 3: HEALTH — confirm the suite is up

Run `docker compose ps --format json` and classify each service the same way
`fah_helpers.py`'s `health_status()` does: any of `unhealthy`/`exited`/
`dead`/`stopped` in the state/health text → **down**; `healthy` → up; else
`running` counts as up — **except** the DB containers below, where `running`
alone is not enough.

**DB containers in `DB_DEPLOY_TYPE`** (`dirdb-main`=router,
`dirdb-data1`=data1, `dirdb-data2`=data2, `dirdb-cis`=CIS,
`dirdb-avod1`=avod1): the stock `mysql:8.0` image reports `running` the
moment bootstrap starts, before it accepts connections — `docker compose ps`
alone is a false positive on fresh volumes. For each such container, run
this exact command yourself and check its exit code:

```
docker exec <container> bash -c 'exec 3<>/dev/tcp/127.0.0.1/3306'
```

- Exit code `0` → that DB is ready.
- Nonzero → not ready yet. Wait, then run the same command again. Keep
  doing this — no short fixed timeout — reporting which DB(s) are still
  initializing and elapsed time each round, never a silent wait.
- Escalate to **down** only if `docker compose ps` shows `exited`/`dead`
  for that container, or the wait runs far past any bootstrap seen in this
  env.

`AWS` DB entries start no local container and skip this probe entirely.

Poll until every service in `DEPLOY_TYPE` is up, then report — this skill's
job ends here.

## Output Format

Use this output every time:

```md
# Docker Director2 Deploy

## Config
[DB_DEPLOY_TYPE used; which service set to local]

## Env State
[VPN: ok | blocked] [containers: reused | rebuilt]

## Health
[all up | listing down services]

## Next Move
[one concrete next step, or "None — env is up, hand off to run scenarios"]
```

## Common Rationalizations

- "The env is probably still healthy from last time" — HEALTH always
  re-polls; a previously-healthy env can have drifted (a sibling ticket's
  deploy, a container restart).
- "Rebuild `harness-mysql-preloaded` every run to be safe" — that's the
  harness skill's concern, not this one; `harness-mysql-preloaded` is a test
  fixture, unrelated to this skill.
- "The image is missing or stale, build/rebuild it here" — no; this skill
  never builds an image. If `--director-version local` doesn't reflect the
  current change, that's the SRE's BUILD step (in `lean-scenario-acceptance`
  DEPLOY, before this skill is called), not something to fix here.
- "DB_DEPLOY_TYPE=AWS is always safe, just default to it" — no; use exactly
  what the caller passed in. A scenario that mutates needs LOCAL DBs (AWS is
  READONLY and the runner blocks the write).
- "Since the env is up, might as well run the scenarios too" — no; that's a
  separate skill's job. This skill reports healthy and stops.

## Red Flags

- It builds, rebuilds, retags, or pushes an image — never this skill's job
- It treats a VPN-down failure as a reason to invent a workaround instead of
  reporting the blocker
- It reports healthy before every `DEPLOY_TYPE` service actually is
- It runs scenarios, reads a report, or renders a verdict — none of that is
  this skill's job

## Verification

- Confirm `environments.env` was written with the correct `DB_DEPLOY_TYPE`
  and the correct service set to `local`
- Confirm HEALTH re-polled and every `DEPLOY_TYPE` service was up before
  reporting done
