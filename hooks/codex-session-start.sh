#!/bin/bash
# Codex wrapper that reuses the existing session-start behavior.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_SCRIPT="$SCRIPT_DIR/session-start.sh"

if [[ -f "$CLAUDE_SCRIPT" ]]; then
  bash "$CLAUDE_SCRIPT"
fi
