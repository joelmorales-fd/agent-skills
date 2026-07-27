#!/bin/bash
# Codex wrapper that adapts apply_patch events to the existing Claude hook.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_HOOK="$SCRIPT_DIR/check-declaration.sh"

mkdir -p "${HOME}/.claude" 2>/dev/null || true

INPUT="$(cat)"
TOOL_NAME="$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')"
PATCH_TEXT="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"
TARGET_FILE="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')"

extract_patch_files() {
  printf '%s\n' "$1" | sed -n \
    -e 's/^\*\*\* Add File: //p' \
    -e 's/^\*\*\* Update File: //p' \
    -e 's/^\*\*\* Delete File: //p' \
    -e 's/^\*\*\* Move to: //p'
}

run_claude_hook() {
  local file_path="$1"
  jq -cn --arg file_path "$file_path" '{tool_input: {file_path: $file_path}}' | bash "$CLAUDE_HOOK"
}

if [[ ! -x "$CLAUDE_HOOK" ]]; then
  echo "agent-skills: missing hook $CLAUDE_HOOK" >&2
  exit 2
fi

if [[ -n "$TARGET_FILE" ]]; then
  run_claude_hook "$TARGET_FILE"
  exit 0
fi

if [[ "$TOOL_NAME" != "apply_patch" ]]; then
  exit 0
fi

matched_any=false
while IFS= read -r patch_file; do
  [[ -n "$patch_file" ]] || continue
  matched_any=true
  run_claude_hook "$patch_file"
done < <(extract_patch_files "$PATCH_TEXT")

if [[ "$matched_any" == "false" ]]; then
  exit 0
fi
