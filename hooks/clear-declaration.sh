#!/bin/bash
# clear-declaration.sh
# Clears the declaration file. Run between tasks.

DECLARATION_FILE="/tmp/claude-declaration.json"

if [[ -f "$DECLARATION_FILE" ]]; then
  rm -f "$DECLARATION_FILE"
  echo "✓ Declaration cleared. Ready for new task."
else
  echo "✓ No declaration to clear. Ready for new task."
fi
