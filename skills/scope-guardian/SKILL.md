---
name: scope-guardian
description: Reviews implementation output for scope creep and unwanted structural changes. Use after any implementation to catch drift before accepting the code. Flags new abstractions, data reshaping, structural changes, and spaghetti patterns.
---

# Scope Guardian

Compare what was asked against what was delivered and flag any deviation.

This skill does not write code. It does not suggest improvements. It only audits and reports.

## When to Use

- After any implementation, before accepting the code
- When comparing delivered code against a declaration or spec
- When checking for scope creep or feature drift
- When auditing for unwanted structural changes

## The Audit Checklist

### 1. Scope Creep

- [ ] **Files touched** — Were only declared files modified?
- [ ] **Functions added** — Were only declared functions added?
- [ ] **Lines changed** — Is the change size proportional to the task?

**Flag if:** Any file was touched that wasn't in the declaration. Any "bonus" functionality was added.

### 2. Unwanted Abstractions

- [ ] **New classes** — Was a class created when a function would suffice?
- [ ] **New interfaces/protocols** — Was an abstraction layer added?
- [ ] **New base classes** — Was inheritance introduced?
- [ ] **New factories/builders** — Was indirection added?

**Flag if:** Any new type was created that wasn't explicitly requested.

### 3. Data Reshaping

- [ ] **Input types** — Does the new code accept the same input shape as before?
- [ ] **Output types** — Does the new code return the same output shape as before?
- [ ] **Intermediate types** — Were dicts converted to dataclasses? Lists to tuples?

**Flag if:** Any data type was changed without explicit request. The rule: "If input was dict, output is dict."

### 4. Structural Changes

- [ ] **Flattening** — Was a hierarchy collapsed into one level?
- [ ] **Depth added** — Were new layers added to flat code?
- [ ] **Module boundaries** — Were files merged or split without request?

**Flag if:** The code structure changed in ways not required by the task.

### 5. Spaghetti Detection

- [ ] **Call depth** — Does the new code add more than 2 levels of call depth?
- [ ] **Side effects** — Are mutations buried in helpers instead of visible at call site?
- [ ] **God functions** — Are there functions doing multiple unrelated things?

**Flag if:** New code requires tracing through 3+ functions to understand.

### 6. Modularity Violations

**Size limits:**
| Unit | Max Lines |
|------|-----------|
| Function | ~50 |
| Class | ~300 |
| File | ~500 |

**Flag if:** 
- Task asked for "add a function" → got a 500-line class
- Task asked for "simple feature" → got a monolithic file

### 7. Cryptic Variable Names

**Flag if:** Any variable name requires reading surrounding code to understand.

| Bad | Good |
|-----|------|
| `d`, `data` | `user_data`, `request_payload` |
| `res`, `result` | `validation_result`, `api_response` |
| `tmp` | `unprocessed_items`, `cached_value` |

### 8. Extra Machinery

- [ ] **Config for constants** — Were literal values turned into config?
- [ ] **Retry/fallback logic** — Was defensive code added that wasn't requested?
- [ ] **Logging** — Was logging added that doesn't help debugging?

**Flag if:** Any machinery was added "just in case" or "for completeness."

### 9. Fake Completion (Hard-Coded to Pass)

- [ ] **Magic numbers** — Are there values that match test expectations exactly?
- [ ] **Test-specific logic** — Are there `if` conditions that only handle known test cases?
- [ ] **Fake returns** — Does the function return the expected output without real computation?

**Detection questions:**
1. Would this code work with inputs NOT in the test?
2. Could you add a new valid test case without changing the code?
3. Are there magic numbers that match test data exactly?

## Output Format

```markdown
## Scope Guardian Audit

### Declaration
[What was asked / declared scope]

### Delivered
[What was actually implemented]

### Findings

#### ✅ Within Scope
- [List items that match the declaration]

#### ⚠️ Scope Concerns
- [List items that may exceed scope - needs user decision]

#### ❌ Scope Violations
- [List items that clearly exceed what was asked]

#### 📏 Modularity Check
- [ ] Functions ≤50 lines: [yes/no]
- [ ] Classes ≤300 lines: [yes/no]
- [ ] Single responsibility: [yes/no]

#### 📝 Naming Check
- [ ] No cryptic abbreviations: [yes/no]
- [ ] Names are self-documenting: [yes/no]

#### 🎭 Fake Completion Check
- [ ] Works with inputs beyond test cases: [yes/no]
- [ ] No magic numbers matching test data: [yes/no]

### Verdict

[PASS | REVIEW | FAIL]

- **PASS**: Implementation matches declaration exactly
- **REVIEW**: Minor concerns that user should verify
- **FAIL**: Scope violations — recommend rejecting
```
