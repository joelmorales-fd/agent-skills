#!/bin/bash
# turn-guard.sh — Automatic context overflow prevention
# Runs on every Stop event, counts turns, warns/blocks as needed

set -e

INPUT=$(cat)
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path')

# Count user messages (turns) in transcript
if [ -f "$TRANSCRIPT" ]; then
  TURNS=$(grep -c '"role":"user"' "$TRANSCRIPT" 2>/dev/null || echo "0")
else
  TURNS=0
fi

# At 40+ turns: Strong warning (no block)
if [ "$TURNS" -ge 40 ]; then
  jq -nc --arg turns "$TURNS" '{
    hookSpecificOutput: {
      hookEventName: "Stop",
      additionalContext: ("🔴 CRITICAL: At " + $turns + " turns — context overflow risk is high. Run /compact soon or start fresh session.")
    }
  }'

# At 30+ turns: Warning via additionalContext
elif [ "$TURNS" -ge 30 ]; then
  jq -nc --arg turns "$TURNS" '{
    hookSpecificOutput: {
      hookEventName: "Stop",
      additionalContext: ("⚠️ At " + $turns + " turns. Consider running /compact soon.")
    }
  }'

# At 20+ turns: Gentle reminder
elif [ "$TURNS" -ge 20 ]; then
  jq -nc --arg turns "$TURNS" '{
    hookSpecificOutput: {
      hookEventName: "Stop",
      additionalContext: ("Note: At " + $turns + " turns. Consider /compact soon.")
    }
  }'
fi

# Under 20 turns: exit silently (no output)
exit 0
