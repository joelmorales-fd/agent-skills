#!/bin/bash
# Codex wrapper that adapts apply_patch and exec_command events
# to the existing Claude declaration hook.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_HOOK="$SCRIPT_DIR/check-declaration.sh"

mkdir -p "${HOME}/.claude" 2>/dev/null || true

INPUT="$(cat)"
TOOL_NAME="$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')"
PATCH_TEXT="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"
TARGET_FILE="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')"

extract_exec_command() {
  printf '%s' "$INPUT" | jq -r '
    .tool_input.cmd // .tool_input.command //
    (
      .tool_input.arguments? |
      if type == "string" then
        (try (fromjson | .cmd // .command // empty) catch empty)
      elif type == "object" then
        .cmd // .command // empty
      else
        empty
      end
    ) //
    (
      .arguments? |
      if type == "string" then
        (try (fromjson | .cmd // .command // empty) catch empty)
      elif type == "object" then
        .cmd // .command // empty
      else
        empty
      end
    ) //
    empty
  '
}

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

extract_shell_write_targets() {
  local shell_command="$1"

  if ! command -v python3 >/dev/null 2>&1; then
    return 0
  fi

  SHELL_COMMAND="$shell_command" python3 - <<'PY'
import os
import shlex


def split_segments(tokens: list[str]) -> list[list[str]]:
    separators = {"&&", "||", ";", "|", "&"}
    current: list[str] = []
    segments: list[list[str]] = []
    for token in tokens:
        if token in separators:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def skip_assignments(tokens: list[str]) -> list[str]:
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if "=" in token and not token.startswith("-"):
            key = token.split("=", 1)[0]
            if key.replace("_", "a").isalnum() and (key[0].isalpha() or key[0] == "_"):
                index += 1
                continue
        break
    return tokens[index:]


def non_option_args(args: list[str]) -> list[str]:
    return [arg for arg in args if arg and not arg.startswith("-")]


def parse_redirections(tokens: list[str]) -> list[str]:
    targets: list[str] = []
    redirect_tokens = {">", ">>", "1>", "1>>", "2>", "2>>"}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in redirect_tokens and index + 1 < len(tokens):
            targets.append(tokens[index + 1])
            index += 2
            continue
        for prefix in ("1>>", "2>>", ">>", "1>", "2>", ">"):
            if token.startswith(prefix) and len(token) > len(prefix):
                targets.append(token[len(prefix):])
                break
        index += 1
    return targets


def parse_perl_targets(args: list[str]) -> list[str]:
    inline = any(arg == "-i" or (arg.startswith("-") and "i" in arg[1:]) for arg in args)
    if not inline:
        return []

    files: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in {"-e", "-E", "-M", "-m"}:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        files.append(token)
        index += 1

    if len(files) <= 1:
        return []
    return files[1:]


def parse_sed_targets(args: list[str]) -> list[str]:
    inplace = any(
        arg == "-i" or arg.startswith("-i") or arg == "--in-place"
        for arg in args
    )
    if not inplace:
        return []

    files: list[str] = []
    skip_next = False
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if token in {"-e", "-f"}:
            skip_next = True
            continue
        if token == "-i":
            continue
        if token.startswith("-"):
            continue
        files.append(token)

    if len(files) <= 1:
        return []
    return files[1:]


def parse_targets(segment: list[str]) -> list[str]:
    segment = skip_assignments(segment)
    if not segment:
        return []

    command = segment[0]
    args = segment[1:]
    targets = parse_redirections(segment)

    if command in {"touch", "mkdir"}:
        targets.extend(non_option_args(args))
    elif command in {"cp", "mv", "install", "ln"}:
        positional = non_option_args(args)
        if positional:
            targets.append(positional[-1])
    elif command == "tee":
        targets.extend(non_option_args(args))
    elif command == "perl":
        targets.extend(parse_perl_targets(args))
    elif command == "sed":
        targets.extend(parse_sed_targets(args))

    cleaned: list[str] = []
    for target in targets:
        if not target or target == "-":
            continue
        cleaned.append(target)
    return cleaned


command = os.environ.get("SHELL_COMMAND", "")
if not command:
    raise SystemExit(0)

try:
    tokens = shlex.split(command, posix=True)
except ValueError:
    raise SystemExit(0)

seen: set[str] = set()
for segment in split_segments(tokens):
    for target in parse_targets(segment):
        if target in seen:
            continue
        seen.add(target)
        print(target)
PY
}

if [[ ! -x "$CLAUDE_HOOK" ]]; then
  echo "agent-skills: missing hook $CLAUDE_HOOK" >&2
  exit 2
fi

if [[ -n "$TARGET_FILE" ]]; then
  run_claude_hook "$TARGET_FILE"
  exit 0
fi

if [[ "$TOOL_NAME" == "apply_patch" ]]; then
  matched_any=false
  while IFS= read -r patch_file; do
    [[ -n "$patch_file" ]] || continue
    matched_any=true
    run_claude_hook "$patch_file"
  done < <(extract_patch_files "$PATCH_TEXT")

  if [[ "$matched_any" == "false" ]]; then
    exit 0
  fi
fi

if [[ "$TOOL_NAME" != "exec_command" && "$TOOL_NAME" != "exec" && "$TOOL_NAME" != "functions.exec_command" ]]; then
  exit 0
fi

EXEC_COMMAND="$(extract_exec_command)"
[[ -n "$EXEC_COMMAND" ]] || exit 0

matched_any=false
while IFS= read -r target; do
  [[ -n "$target" ]] || continue
  matched_any=true
  run_claude_hook "$target"
done < <(extract_shell_write_targets "$EXEC_COMMAND")

if [[ "$matched_any" == "false" ]]; then
  exit 0
fi
