---
name: checkpoint
description: Create a session checkpoint for handoff. Use before /compact, ending a session, or switching tasks.
disable-model-invocation: true
allowed-tools: Bash(mkdir *) Write
---

# Create Session Checkpoint

!`${CLAUDE_SKILL_DIR}/scripts/create.sh`

The checkpoint file has been created. Now fill in the placeholder sections:
- **Current Task**: What were you working on?
- **Next Step**: What should happen next?

Then tell the user:
```
✓ Checkpoint saved to .handoff/checkpoint-[date].md

To continue in a NEW session:
1. Start fresh session  
2. Say: "Read .handoff/checkpoint-[date].md and continue"
```
