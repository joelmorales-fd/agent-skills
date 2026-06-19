#!/bin/bash
# create.sh — Create a handoff document for session continuity

set -e

DIR=$(pwd)
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)
BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

mkdir -p "$DIR/.handoff"

GIT_STATUS=$(git status --short 2>/dev/null || echo "Not a git repo")
RECENT_COMMITS=$(git log --oneline -5 2>/dev/null || echo "No commits")

CHECKPOINT_FILE="$DIR/.handoff/checkpoint-$DATE.md"

cat > "$CHECKPOINT_FILE" << EOF
# Session Checkpoint

**Created**: $DATE $TIME
**Working Directory**: $DIR
**Branch**: $BRANCH

## Git Status
\`\`\`
$GIT_STATUS
\`\`\`

## Recent Commits
\`\`\`
$RECENT_COMMITS
\`\`\`

## Current Task
<!-- Fill in: What were you working on? -->

## Progress
- [ ] <!-- Fill in: What's done and what remains? -->

## Key Decisions Made
1. <!-- Decision — Why -->

## Next Step
<!-- Exact next action to take -->

---

## Resume Instructions

**To continue this work:**

1. \`cd $DIR\`
2. Read this checkpoint
3. Continue from "Next Step"

**Do NOT:**
- Re-debate decisions already made
- Start over from scratch
EOF

echo "✓ Checkpoint saved: $CHECKPOINT_FILE"
