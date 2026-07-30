#!/bin/bash
# clear-declaration.sh
# Clears the declaration file. Run between tasks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "${DECLARATION_CLIENT:-}" && -n "${CLAUDE_CODE_SESSION_ID:-}" ]]; then
  DECLARATION_CLIENT="claude"
fi

if [[ -z "${DECLARATION_SESSION_ID:-}" && -n "${CLAUDE_CODE_SESSION_ID:-}" ]]; then
  DECLARATION_SESSION_ID="$CLAUDE_CODE_SESSION_ID"
fi

if [[ -z "${DECLARATION_CWD:-}" ]]; then
  DECLARATION_CWD="$(pwd)"
fi

DECLARATION_FILE="${DECLARATION_FILE:-$(bash "$SCRIPT_DIR/resolve-declaration-file.sh")}"

if [[ -f "$DECLARATION_FILE" ]]; then
  rm -f "$DECLARATION_FILE"
  echo "✓ Declaration cleared. Ready for new task."
else
  echo "✓ No declaration to clear. Ready for new task."
fi
