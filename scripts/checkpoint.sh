#!/bin/bash
# checkpoint.sh — Create a handoff document for session continuity
# Usage: ./scripts/checkpoint.sh

set -e

DIR=$(pwd)
TIMESTAMP=$(date +%Y-%m-%d-%H%M)
TIME=$(date +%H:%M)
DATE=$(date +%Y-%m-%d)
BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

mkdir -p "$DIR/.handoff"

GIT_STATUS=$(git status --short 2>/dev/null || echo "Not a git repo")
RECENT_COMMITS=$(git log --oneline -5 2>/dev/null || echo "No commits")

CHECKPOINT_FILE="$DIR/.handoff/checkpoint-$TIMESTAMP.md"

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
echo ""
echo "To resume, tell Claude:"
echo "  Read $CHECKPOINT_FILE and continue"
