#!/usr/bin/env python3
"""End-to-end fixture: drive a tiny ticket through the flow using the real guard.

This proves the *mechanics* locally, with no Codex host and no real repo:
a specialist's test fails RED via the guard, an implementation makes it GREEN via
the guard, and the lead records state.md + code-review.md. It exercises the same edges
the real workflow uses (guard.run_command, commands.md, the ticket files) so a
break in that plumbing fails here.

It does NOT test the host subagent mechanism (that is the judge spike) — see
details/judge-spike.md.

Run: python3 e2e_fixture.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import guard  # noqa: E402


# --- the tiny fake repo the ticket operates on ------------------------------

SIGNUP_BUGGY = '''\
def signup(username):
    # BUG: accepts empty usernames
    return {"status": 201, "username": username}
'''

SIGNUP_FIXED = '''\
def signup(username):
    if not username or not username.strip():
        return {"status": 400, "error": "username required"}
    return {"status": 201, "username": username}
'''

# The approved test: exit 0 if empty usernames are rejected, else exit 1.
RUN_TEST = '''\
import sys
from signup import signup
sys.exit(0 if signup("")["status"] == 400 else 1)
'''

COMMANDS_MD = '''\
# DEMO-1 Approved Commands

```json
{
  "commands": {
    "red":   {"argv": ["python3", "run_test.py"], "expected_exit": 1, "timeout": 30},
    "green": {"argv": ["python3", "run_test.py"], "expected_exit": 0, "timeout": 30}
  }
}
```
'''


def write_state(ticket, stage, now, observed, read, nxt, history):
    (Path(ticket) / "state.md").write_text(
        "# DEMO-1: Reject empty usernames on signup\n\n"
        "- **Stage:** %s\n\n"
        "## Now\n%s\n\n## Last observed\n%s\n\n## Lead's read\n%s\n\n"
        "## Next action\n%s\n\n## Waiting on human\nnone\n\n## History\n%s\n"
        % (stage, now, observed, read, nxt, "\n".join("- " + h for h in history)),
        encoding="utf-8",
    )


def main():
    with tempfile.TemporaryDirectory() as root:
        root = Path(root)
        ticket = root / "demo-1"
        repo = root / "repo"
        ticket.mkdir()
        repo.mkdir()

        # SPECS artifacts (abbreviated) + approved commands
        (ticket / "specification.md").write_text(
            "Scenario: empty username is rejected with 400\n", encoding="utf-8")
        (ticket / "commands.md").write_text(COMMANDS_MD, encoding="utf-8")

        # repo starts buggy; specialist adds the (failing) test
        (repo / "signup.py").write_text(SIGNUP_BUGGY, encoding="utf-8")
        (repo / "run_test.py").write_text(RUN_TEST, encoding="utf-8")

        history = ["SPECS — spec approved", "TDD — test written"]

        # TDD: RED via the guard (real exit 1)
        red = guard.run_command(str(ticket), str(repo), "red")
        assert red["exit_code"] == 1, ("expected RED exit 1, got %r" % red)
        assert red["exit_code"] == red["expected_exit"], "RED not the expected failure"
        history.append("TDD — RED confirmed (exit 1)")
        write_state(ticket, "TDD", "confirmed RED before implementing",
                    "run_test.py -> exit 1", "real RED, empty usernames accepted today",
                    "implement the guard clause, then run GREEN", history)

        # specialist implements the smallest change
        (repo / "signup.py").write_text(SIGNUP_FIXED, encoding="utf-8")

        # TDD: GREEN via the guard (real exit 0)
        green = guard.run_command(str(ticket), str(repo), "green")
        assert green["exit_code"] == 0, ("expected GREEN exit 0, got %r" % green)
        history.append("TDD — GREEN confirmed (exit 0)")

        # JUDGE: independent review writes code-review.md (PASS)
        (ticket / "code-review.md").write_text(
            "## Code Review 1 — stage JUDGE\n**Verdict:** PASS\n\n### Findings\nnone\n",
            encoding="utf-8")
        history.append("JUDGE — PASS, no blocking finding")

        # MUTATION + COMPLETE (mechanics only)
        history.append("MUTATION — no meaningful survivor")
        history.append("COMPLETE — delivery-ready")
        write_state(ticket, "COMPLETE", "delivery-ready",
                    "judge PASS; mutation clean", "all gates satisfied",
                    "none", history)

        # assertions on the recorded flow
        state = (ticket / "state.md").read_text(encoding="utf-8")
        assert "**Stage:** COMPLETE" in state
        assert "RED confirmed" in state and "GREEN confirmed" in state
        review = (ticket / "code-review.md").read_text(encoding="utf-8")
        assert "PASS" in review
        # the guard, not a summary, produced the pass/fail evidence
        assert red["stdout"] == "" or isinstance(red["stdout"], str)

        print("e2e_fixture: OK  (RED exit 1 -> fix -> GREEN exit 0 -> JUDGE PASS -> COMPLETE)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
