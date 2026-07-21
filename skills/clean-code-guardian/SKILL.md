---
name: clean-code-guardian
description: Enforces clean, pattern-matched code that fits the codebase. Use when you want code that matches existing patterns, adds no hidden abstractions, reshapes no data, and stays modular. Reviews implementations for structural violations.
---

# Clean Code Guardian

Audit code for structural violations. Check that new code matches the codebase's existing patterns and adds no unwanted complexity.

This skill does not write code. It verifies that code fits.

## When to Use

- After any implementation, before accepting the code
- When reviewing code for pattern compliance
- When checking for unwanted abstractions or complexity
- When auditing for hard-coded values or fake completion

## The Contract

New code must follow these rules. Flag any violation.

### Never Added (Unless Explicitly Requested)

| Violation | Description | How to Spot |
|-----------|-------------|-------------|
| **Hard-coded values to pass** | Magic numbers, specific strings, or logic that only works for test cases | Values that match test data exactly; logic that wouldn't work for other inputs |
| **New abstraction** | Class, interface, protocol, base class | `class`, `interface`, `Protocol`, `ABC` keywords |
| **New file** | Code should go in existing files first | New file created |
| **Data reshaping** | Changing dict→dataclass, list→tuple, etc. | Type annotations differ from existing code |
| **Flattening** | Collapsing a hierarchy | Nested structure → flat structure |
| **Adding depth** | New layers in flat code | Flat code → nested structure |
| **Extra fallbacks** | Retry logic, defensive code | `try/except` blocks not in original |
| **Boilerplate** | Unused `__init__`, `toString`, logging | Methods that aren't called |
| **Config for constants** | Fixed values turned into config | New config keys for unchanging values |
| **Explanatory comments** | Comments explaining WHAT not WHY | Comments on obvious code |

### Critical: No Hard-Coding to Pass Tasks

**This is a major violation.** The LLM often hard-codes values to make tests pass or to "complete" a task without solving it properly.

**Signs of hard-coding to pass:**
- Magic numbers that match test data exactly
- String comparisons against specific test values
- `if` conditions that only handle the test cases
- Logic that would fail with different (valid) inputs
- Return values that match expected test output without real computation

**Detection questions:**
1. Would this code work with inputs NOT in the test?
2. Are there magic numbers that match test expectations exactly?
3. Is the logic general or specific to known cases?
4. Could you add a new test case and have it pass without code changes?

### Critical: No Giant Classes/Files (Modularity)

**Size limits:**
- **Function:** Max ~50 lines
- **Class:** Max ~200-300 lines
- **File:** Max ~500 lines

**Signs of modularity violation:**
- Class with 10+ methods that do unrelated things
- File with 1000+ lines
- Function with 5+ levels of nesting
- God class that "manages" or "handles" everything
- Mixing I/O with business logic in the same class

### Critical: Meaningful Variable Names

**Forbidden naming patterns:**

| Bad | Good Alternative |
|-----|------------------|
| `x`, `y`, `z` | `width`, `height`, `depth` |
| `tmp`, `temp` | `unprocessed_items`, `cached_response` |
| `val`, `value` | `user_age`, `total_price` |
| `res`, `result` | `validation_result`, `api_response` |
| `d`, `data` | `user_data`, `request_payload` |

**Rule: Names must be self-documenting.** A reader should understand what a variable holds without reading surrounding code.

### Always Required

| Requirement | How to Verify |
|-------------|---------------|
| **Pattern match** | Find 2 existing examples of same type, compare |
| **Same naming style** | New names follow existing conventions |
| **Same error handling** | Errors handled like neighboring code |
| **Shallow call chains** | New code adds ≤2 levels of call depth |
| **Surface side effects** | Mutations visible at call site, not buried |
| **Modular size** | Functions ≤50 lines, classes ≤300 lines, files ≤500 lines |
| **Single responsibility** | Each unit has one reason to change |
| **Meaningful names** | No short/cryptic names |

## Output Format

```markdown
## Clean Code Audit

### Files Reviewed
- [file1.py]
- [file2.py]

### Findings

#### ✅ Pattern Compliance
- [What matches existing patterns]

#### ❌ Violations
- [Specific file:line + violation type + fix]

### Modularity Check
- [ ] Functions ≤50 lines: [yes/no]
- [ ] Classes ≤300 lines: [yes/no]
- [ ] Single responsibility: [yes/no]

### Naming Check
- [ ] No cryptic abbreviations: [yes/no]
- [ ] Names are self-documenting: [yes/no]

### Fake Completion Check
- [ ] Works with inputs beyond test cases: [yes/no]
- [ ] No magic numbers matching test data: [yes/no]

### Verdict
[CLEAN | NEEDS FIX | REJECT]
```
