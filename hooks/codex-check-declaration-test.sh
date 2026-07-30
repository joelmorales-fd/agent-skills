#!/bin/bash
# Small smoke test for the Codex declaration wrapper.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/codex-check-declaration.sh"
RESOLVER="$SCRIPT_DIR/resolve-declaration-file.sh"
BACKUP_FILE=""
TEST_HOME="$(mktemp -d)"
export DECLARATION_CLIENT="codex"
export DECLARATION_SESSION_ID="test-session"
export DECLARATION_CWD="/tmp/test-project"
DECLARATION_FILE="$(bash "$RESOLVER")"

cleanup() {
  rm -rf "$TEST_HOME"
  if [[ -n "$BACKUP_FILE" && -f "$BACKUP_FILE" ]]; then
    mv "$BACKUP_FILE" "$DECLARATION_FILE"
  else
    rm -f "$DECLARATION_FILE"
  fi
}
trap cleanup EXIT

if [[ -f "$DECLARATION_FILE" ]]; then
  BACKUP_FILE="$(mktemp /tmp/claude-declaration.backup.XXXXXX)"
  cp "$DECLARATION_FILE" "$BACKUP_FILE"
fi

cat > "$DECLARATION_FILE" <<'EOF'
{
  "task": "codex hook smoke test",
  "files_to_touch": ["allowed.txt"],
  "approved": true
}
EOF

allowed_payload='{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Update File: allowed.txt\n@@\n-old\n+new\n*** End Patch\n"}}'
blocked_payload='{"tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch\n*** Update File: blocked.txt\n@@\n-old\n+new\n*** End Patch\n"}}'
allowed_exec_payload='{"tool_name":"exec_command","tool_input":{"cmd":"touch allowed.txt"}}'
blocked_exec_payload='{"tool_name":"exec_command","tool_input":{"cmd":"cp source.txt blocked.txt"}}'
read_only_exec_payload='{"tool_name":"exec_command","tool_input":{"cmd":"ls -la"}}'

printf '%s' "$allowed_payload" | HOME="$TEST_HOME" bash "$HOOK"
printf '%s' "$allowed_exec_payload" | HOME="$TEST_HOME" bash "$HOOK"
printf '%s' "$read_only_exec_payload" | HOME="$TEST_HOME" bash "$HOOK"

set +e
printf '%s' "$blocked_payload" | HOME="$TEST_HOME" bash "$HOOK" >/dev/null 2>&1
status=$?
set -e

if [[ "$status" -ne 2 ]]; then
  echo "expected blocked patch to exit 2, got $status" >&2
  exit 1
fi

set +e
printf '%s' "$blocked_exec_payload" | HOME="$TEST_HOME" bash "$HOOK" >/dev/null 2>&1
status=$?
set -e

if [[ "$status" -ne 2 ]]; then
  echo "expected blocked shell write to exit 2, got $status" >&2
  exit 1
fi

echo "codex-check-declaration smoke test passed"
