#!/bin/bash
# turn-guard.sh — Automatic context overflow prevention
# Runs on every Stop event, counts turns SINCE LAST COMPACTION

set -e

INPUT=$(cat)
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path')
PROJECT_DIR=$(echo "$INPUT" | jq -r '.session_id // empty' | xargs dirname 2>/dev/null || pwd)

# Try to get project dir from env or fall back to pwd
if [ -n "$CLAUDE_PROJECT_DIR" ]; then
  PROJECT_DIR="$CLAUDE_PROJECT_DIR"
else
  PROJECT_DIR=$(pwd)
fi

# Count user messages (turns) since last compaction
if [ -f "$TRANSCRIPT" ]; then
  # Find last compaction marker (away_summary = /compact result)
  LAST_COMPACT=$(grep -n '"subtype":"away_summary"' "$TRANSCRIPT" 2>/dev/null | tail -1 | cut -d: -f1)
  
  if [ -n "$LAST_COMPACT" ]; then
    # Count turns AFTER compaction
    # Try session format first ("type":"user"), fall back to history format ("display")
    TURNS=$(tail -n +"$LAST_COMPACT" "$TRANSCRIPT" | grep -c '"type":"user"' 2>/dev/null || tail -n +"$LAST_COMPACT" "$TRANSCRIPT" | grep -c '"display"' 2>/dev/null || echo "0")
  else
    # No compaction yet - count all turns
    # Try session format first ("type":"user"), fall back to history format ("display")
    TURNS=$(grep -c '"type":"user"' "$TRANSCRIPT" 2>/dev/null || grep -c '"display"' "$TRANSCRIPT" 2>/dev/null || echo "0")
  fi
else
  TURNS=0
fi

# Auto-create checkpoint at 70+ turns
create_checkpoint() {
  local DIR="$PROJECT_DIR"
  local TIMESTAMP=$(date +%Y-%m-%d-%H%M)
  local TIME=$(date +%H:%M)
  local DATE=$(date +%Y-%m-%d)
  local BRANCH=$(cd "$DIR" && git branch --show-current 2>/dev/null || echo "unknown")
  local GIT_STATUS=$(cd "$DIR" && git status --short 2>/dev/null || echo "Not a git repo")
  local RECENT=$(cd "$DIR" && git log --oneline -5 2>/dev/null || echo "No commits")
  
  mkdir -p "$DIR/.handoff"
  
  cat > "$DIR/.handoff/checkpoint-$TIMESTAMP.md" << EOF
# Session Checkpoint (Auto-created at $TURNS turns)

**Created**: $DATE $TIME
**Working Directory**: $DIR
**Branch**: $BRANCH

## Git Status
\`\`\`
$GIT_STATUS
\`\`\`

## Recent Commits
\`\`\`
$RECENT
\`\`\`

## Current Task
<!-- Fill in: What were you working on? -->

## Next Step
<!-- Fill in: What to do next -->
EOF
  
  echo "$DIR/.handoff/checkpoint-$TIMESTAMP.md"
}

# At 70+ turns: Strong warning + auto-checkpoint
if [ "$TURNS" -ge 70 ]; then
  CHECKPOINT=$(create_checkpoint)
  jq -nc --arg turns "$TURNS" --arg cp "$CHECKPOINT" '{
    hookSpecificOutput: {
      hookEventName: "Stop",
      additionalContext: ("🔴 CRITICAL: At " + $turns + " turns. Auto-checkpoint saved to " + $cp + ". Run /compact or start fresh.")
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
