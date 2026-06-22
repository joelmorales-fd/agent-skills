---
name: interview-me
mode: compact
---

# interview-me — Compact

## Trigger
- The ask is underspecified
- You are about to guess who the user is, why they want this, what success looks like, or what the real constraint is
- The user named a solution shape, but the actual problem is still unclear

## Core Rule
- Ask exactly one question at a time
- Attach one best guess
- Wait for the reply before asking the next question

## Always Do
- Start from what the user already told you
- Ask about the highest-uncertainty point, not everything at once
- Keep the question upstream of implementation when the brief is still pre-spec
- Use the guess to surface your assumption so the user can correct it quickly

## Never Do
- Do not ask for details the user already provided
- Do not ask a batch of questions
- Do not jump to stack, framework, database, file layout, or implementation planning
- Do not produce a spec, task plan, or code before the intent is clear

## Question Shape
```text
Q: <one focused question>
GUESS: <your best guess and why>
```

## Stop Condition
- Stop when you can predict the user's reaction to the next three questions
- Then restate the intent clearly and ask for confirmation

---

→ **Full guidance**: `skills/interview-me/SKILL.md`
