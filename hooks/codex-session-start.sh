#!/bin/bash
# Codex wrapper that adapts the Claude session-start payload to Codex format.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_SCRIPT="$SCRIPT_DIR/session-start.sh"

if [[ ! -f "$CLAUDE_SCRIPT" ]]; then
  exit 0
fi

payload="$(bash "$CLAUDE_SCRIPT")"
[[ -n "$payload" ]] || exit 0

if command -v jq >/dev/null 2>&1; then
  message="$(printf '%s' "$payload" | jq -r '.message // empty')"
elif command -v python3 >/dev/null 2>&1; then
  message="$(PAYLOAD="$payload" python3 - <<'PY'
import json
import os

try:
    data = json.loads(os.environ["PAYLOAD"])
except Exception:
    print("")
else:
    print(data.get("message", ""))
PY
)"
else
  exit 0
fi

[[ -n "$message" ]] || exit 0

if command -v jq >/dev/null 2>&1; then
  jq -cn --arg message "$message" \
    '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $message}}'
else
  MESSAGE="$message" python3 - <<'PY'
import json
import os

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": os.environ["MESSAGE"],
    }
}))
PY
fi
