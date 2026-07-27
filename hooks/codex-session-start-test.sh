#!/bin/bash
# Small smoke test for the Codex SessionStart wrapper.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
payload="$(bash "$SCRIPT_DIR/codex-session-start.sh")"

PAYLOAD="$payload" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["PAYLOAD"])
output = payload["hookSpecificOutput"]

if output["hookEventName"] != "SessionStart":
    raise SystemExit(f"expected SessionStart, got {output['hookEventName']}")

context = output["additionalContext"]
if "agent-skills loaded." not in context:
    raise SystemExit("missing startup preface")
if "# Using Agent Skills" not in context:
    raise SystemExit("missing using-agent-skills content")

print("codex-session-start JSON payload OK")
PY
