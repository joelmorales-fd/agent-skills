#!/bin/bash
# turn-guard.sh — Automatic context overflow prevention
# Runs on every Stop event, counts turns SINCE LAST COMPACTION

set -e

INPUT=$(cat)
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path')

# Count user messages (turns) since last compaction
if [ -f "$TRANSCRIPT" ]; then
  # Find last compaction marker (conversation-summary)
  LAST_COMPACT=$(grep -n 'conversation-summary' "$TRANSCRIPT" 2>/dev/null | tail -1 | cut -d: -f1)
  
  if [ -n "$LAST_COMPACT" ]; then
    # Count turns AFTER compaction
    TURNS=$(tail -n +"$LAST_COMPACT" "$TRANSCRIPT" | grep -c '"role":"user"' 2>/dev/null || echo "0")
  else
    # No compaction yet - count all turns
    TURNS=$(grep -c '"role":"user"' "$TRANSCRIPT" 2>/dev/null || echo "0")
  fi
else
  TURNS=0
fi

# At 70+ turns: Strong warning (no block)
if [ "$TURNS" -ge 70 ]; then
  jq -nc --arg turns "$TURNS" '{
    hookSpecificOutput: {
      hookEventName: "Stop",
      additionalContext: ("🔴 CRITICAL: At " + $turns + " turns — context overflow risk is high. Run /compact soon or start fresh session.")
    }
  }'

# At 50+ turns: Warning via additionalContext
elif [ "$TURNS" -ge 50 ]; then
  jq -nc --arg turns "$TURNS" '{
    hookSpecificOutput: {
      hookEventName: "Stop",
      additionalContext: ("⚠️ At " + $turns + " turns. Consider running /compact soon.")
    }
  }'

# At 40+ turns: Gentle reminder
elif [ "$TURNS" -ge 40 ]; then
  jq -nc --arg turns "$TURNS" '{
    hookSpecificOutput: {
      hookEventName: "Stop",
      additionalContext: ("Note: At " + $turns + " turns. Consider /compact soon.")
    }
  }'
fi

# Under 40 turns: exit silently (no output)
exit 0
