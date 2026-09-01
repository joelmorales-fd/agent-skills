# <TICKET-ID> Approved Commands

The only commands the guard may run for this ticket. The lead appends entries as
they become known (RED/GREEN in TDD, the deploy before JUDGE). The guard runs an
entry only on **exact** argv match.

No secrets in any entry.

The guard reads the single ```json``` block below — it is the **authoritative**
source. The table under it is the human view; keep them in sync.

```json
{
  "commands": {
    "red":   {"argv": ["pytest", "tests/test_x.py::test_case"], "expected_exit": 1, "timeout": 60},
    "green": {"argv": ["pytest", "tests/test_x.py::test_case"], "expected_exit": 0, "timeout": 60}
  }
}
```

## Commands

| id | argv | expected exit | timeout (s) | added in |
|---|---|---|---|---|
| red | `["pytest","tests/test_x.py::test_case"]` | 1 | 60 | TDD |
| green | `["pytest","tests/test_x.py::test_case"]` | 0 | 60 | TDD |
| deploy | `["<docker/compose command>"]` | 0 | 900 | JUDGE |

<Replace the example rows with this ticket's real commands. Keep argv as an exact
token list — no shell string, no interpolation.>

**director2-aws harness does NOT go here.** The harness (buildenv, the in-docker
clean build, the preloaded image, the sidecar run) is owned by the
`director2-harness-test` skill — invoke that skill; do not put `buildenv`,
`gradlew`, `docker exec`, or `run-harness-sidecar.sh` in `commands.md`. This file
is for simple, self-contained commands only.
