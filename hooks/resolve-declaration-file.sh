#!/bin/bash
# Resolves the active declaration file for the current client/session.

set -euo pipefail

TMP_ROOT="${TMPDIR:-/tmp}"
TMP_ROOT="${TMP_ROOT%/}"
DECLARATION_DIR="$TMP_ROOT/agent-skills-declarations"
CLIENT="${DECLARATION_CLIENT:-}"
SESSION_ID="${DECLARATION_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-}}}"
CWD_PATH="${DECLARATION_CWD:-${PWD:-$(pwd)}}"

mkdir -p "$DECLARATION_DIR"

if [[ -z "$CLIENT" ]]; then
  if [[ -n "${CLAUDE_CODE_SESSION_ID:-}" ]]; then
    CLIENT="claude"
  elif [[ -n "${CODEX_THREAD_ID:-}" ]]; then
    CLIENT="codex"
  else
    CLIENT="agent"
  fi
fi

CLIENT_SLUG="$(printf '%s' "$CLIENT" | tr -cs 'A-Za-z0-9._-' '-')"
SESSION_SLUG="$(printf '%s' "${SESSION_ID:-no-session}" | tr -cs 'A-Za-z0-9._-' '-')"
CWD_HASH="$(printf '%s' "$CWD_PATH" | shasum -a 256 | cut -c1-12)"

printf '%s/%s-%s-%s.json\n' "$DECLARATION_DIR" "$CLIENT_SLUG" "$SESSION_SLUG" "$CWD_HASH"
