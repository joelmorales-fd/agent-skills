#!/bin/bash
# check-declaration.sh
# Blocks writes to files not in the approved declaration.
# Called by Claude Code before every Write/Edit/MultiEdit.
# Receives JSON input via stdin from Claude Code hooks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="${HOME}/.claude/audit.log"

# Audit logging function
log_event() {
  local action=$1
  local file=$2
  local reason=${3:-}
  echo "$(date -Iseconds) | $action | $file | $reason" >> "$LOG_FILE"
}

# Read JSON input from stdin
INPUT=$(cat)

if ! command -v jq >/dev/null 2>&1; then
  log_event "ERROR" "(unknown file)" "jq not installed"
  echo "ERROR: jq is required for declaration checking. Install with: brew install jq" >&2
  exit 2
fi

if [[ -z "${DECLARATION_CLIENT:-}" && -n "${CLAUDE_CODE_SESSION_ID:-}" ]]; then
  DECLARATION_CLIENT="claude"
fi

if [[ -z "${DECLARATION_CLIENT:-}" && -n "${CODEX_THREAD_ID:-}" ]]; then
  DECLARATION_CLIENT="codex"
fi

if [[ -z "${DECLARATION_SESSION_ID:-}" ]]; then
  DECLARATION_SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)"
fi

if [[ -z "${DECLARATION_SESSION_ID:-}" && -n "${CLAUDE_CODE_SESSION_ID:-}" ]]; then
  DECLARATION_SESSION_ID="$CLAUDE_CODE_SESSION_ID"
fi

if [[ -z "${DECLARATION_SESSION_ID:-}" && -n "${CODEX_THREAD_ID:-}" ]]; then
  DECLARATION_SESSION_ID="$CODEX_THREAD_ID"
fi

if [[ -z "${DECLARATION_CWD:-}" ]]; then
  DECLARATION_CWD="$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || true)"
fi

if [[ -z "${DECLARATION_CWD:-}" ]]; then
  DECLARATION_CWD="$(pwd)"
fi

DECLARATION_FILE="${DECLARATION_FILE:-$(bash "$SCRIPT_DIR/resolve-declaration-file.sh")}"

# Extract file path from tool_input.file_path
TARGET_FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')

# If no file path found, allow (might be a non-file tool)
if [[ -z "$TARGET_FILE" ]]; then
  log_event "ALLOW" "(no file path)" "non-file tool"
  exit 0
fi

# Always allow writes to the declaration file itself
if [[ "$TARGET_FILE" == "$DECLARATION_FILE" ]]; then
  log_event "ALLOW" "$TARGET_FILE" "declaration file"
  exit 0
fi

# Always allow writes to temp directories (for safe exploration)
if [[ "$TARGET_FILE" == /tmp/* ]] || [[ "$TARGET_FILE" == /var/folders/* ]]; then
  log_event "ALLOW" "$TARGET_FILE" "temp directory"
  exit 0
fi

# If no declaration exists, block with clear message
if [[ ! -f "$DECLARATION_FILE" ]]; then
  log_event "BLOCK" "$TARGET_FILE" "no declaration found"
  echo "" >&2
  echo "⛔ BLOCKED: No declaration found" >&2
  echo "" >&2
  echo "Before writing any file, you must declare your scope." >&2
  echo "" >&2
  echo "Use /declare or write a declaration to:" >&2
  echo "  $DECLARATION_FILE" >&2
  echo "" >&2
  exit 2
fi

# Validate declaration structure
validate_declaration() {
  local file=$1
  
  # Check required fields exist
  if ! jq -e '.task' "$file" >/dev/null 2>&1; then
    echo "ERROR: Declaration missing required field: task" >&2
    return 1
  fi
  
  if ! jq -e '.files_to_touch' "$file" >/dev/null 2>&1; then
    echo "ERROR: Declaration missing required field: files_to_touch" >&2
    return 1
  fi
  
  if ! jq -e '.approved' "$file" >/dev/null 2>&1; then
    echo "ERROR: Declaration missing required field: approved" >&2
    return 1
  fi
  
  # Check files_to_touch is array
  if ! jq -e '.files_to_touch | type == "array"' "$file" >/dev/null 2>&1; then
    echo "ERROR: files_to_touch must be an array, got: $(jq -r '.files_to_touch | type' "$file" 2>/dev/null || echo 'invalid')" >&2
    return 1
  fi
  
  # Check approved is boolean
  local approved_type=$(jq -r '.approved | type' "$file" 2>/dev/null || echo 'invalid')
  if [[ "$approved_type" != "boolean" ]]; then
    echo "ERROR: approved must be true or false (boolean), got: $approved_type" >&2
    return 1
  fi
  
  return 0
}

if ! validate_declaration "$DECLARATION_FILE"; then
  log_event "BLOCK" "$TARGET_FILE" "invalid declaration structure"
  echo "" >&2
  echo "⛔ BLOCKED: Declaration file is invalid" >&2
  echo "" >&2
  echo "Fix the declaration structure and try again." >&2
  echo "" >&2
  exit 2
fi

# Check if the declaration has been approved
APPROVED=$(jq -r '.approved // false' "$DECLARATION_FILE" 2>/dev/null)
if [[ "$APPROVED" != "true" ]]; then
  log_event "BLOCK" "$TARGET_FILE" "declaration not approved"
  echo "" >&2
  echo "⛔ BLOCKED: Declaration not yet approved" >&2
  echo "" >&2
  echo "User must say 'proceed' to approve the declaration." >&2
  echo "" >&2
  exit 2
fi

# Check if target file is in the approved list
# Handle both absolute paths and relative paths
# Use array to properly handle filenames with spaces (bash 3.x compatible)
approved_files=()
while IFS= read -r line; do
  approved_files+=("$line")
done < <(jq -r '.files_to_touch[]' "$DECLARATION_FILE" 2>/dev/null)

if [[ ${#approved_files[@]} -eq 0 ]]; then
  log_event "BLOCK" "$TARGET_FILE" "no files in files_to_touch"
  echo "" >&2
  echo "⛔ BLOCKED: No files declared in files_to_touch" >&2
  echo "" >&2
  exit 2
fi

for approved_file in "${approved_files[@]}"; do
  # Exact match
  if [[ "$TARGET_FILE" == "$approved_file" ]]; then
    log_event "ALLOW" "$TARGET_FILE" "exact match: $approved_file"
    exit 0
  fi
  
  # Handle relative paths by checking if target ends with approved path
  if [[ "$TARGET_FILE" == *"/$approved_file" ]]; then
    log_event "ALLOW" "$TARGET_FILE" "relative match: $approved_file"
    exit 0
  fi
  
  # Handle case where approved_file is absolute and target matches
  if [[ "$approved_file" == /* ]] && [[ "$TARGET_FILE" == "$approved_file" ]]; then
    log_event "ALLOW" "$TARGET_FILE" "absolute match: $approved_file"
    exit 0
  fi
  
  # Handle glob patterns (e.g., "src/*.py") - basic wildcard support
  if [[ "$approved_file" == *"*"* ]]; then
    # Convert glob to regex for matching
    pattern="${approved_file//\*/.*}"
    if [[ "$TARGET_FILE" =~ $pattern ]]; then
      log_event "ALLOW" "$TARGET_FILE" "glob match: $approved_file"
      exit 0
    fi
  fi
done

# File not in approved list
TASK=$(jq -r '.task // "(no task description)"' "$DECLARATION_FILE" 2>/dev/null)
log_event "BLOCK" "$TARGET_FILE" "file not in declaration"

# Truncate path for display (keep last 3 components)
truncate_path() {
  local path="$1"
  local components=$(echo "$path" | tr '/' '\n' | wc -l)
  if [[ $components -gt 3 ]]; then
    echo "...$(echo "$path" | rev | cut -d'/' -f1-3 | rev)"
  else
    echo "$path"
  fi
}

echo "" >&2
echo "⛔ BLOCKED: File not in declaration" >&2
echo "" >&2
echo "Task: $TASK" >&2
echo "Attempted: $(truncate_path "$TARGET_FILE")" >&2
echo "" >&2
echo "Declared files:" >&2
for f in "${approved_files[@]}"; do
  echo "  • $(truncate_path "$f")" >&2
done
echo "" >&2
echo "To fix:" >&2
echo "  1. Update declaration to include this file" >&2
echo "  2. Set approved=false" >&2
echo "  3. Wait for 'proceed'" >&2
echo "" >&2
exit 2
