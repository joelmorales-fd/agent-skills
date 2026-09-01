#!/usr/bin/env python3
"""Runnable checks for the guard. Run: python3 test_guard.py"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import guard  # noqa: E402


def _ticket(tmp, commands_json):
    d = Path(tmp)
    (d / "commands.md").write_text(
        "# commands\n\n```json\n%s\n```\n" % commands_json, encoding="utf-8"
    )
    return str(d)


def run_command_tests():
    with tempfile.TemporaryDirectory() as tmp:
        t = _ticket(tmp, '{"commands": {"ok": {"argv": ["python3","-c","print(1)"], "expected_exit": 0, "timeout": 30}}}')

        # runs the approved command, returns the real exit code
        r = guard.run_command(t, tmp, "ok")
        assert r["exit_code"] == 0, r
        assert r["stdout"].strip() == "1", r
        assert r["timed_out"] is False

        # unknown id is refused
        try:
            guard.run_command(t, tmp, "missing")
            assert False, "unknown id should fail"
        except guard.GuardError:
            pass

        # argv override must match exactly
        try:
            guard.run_command(t, tmp, "ok", argv_override=["python3", "-c", "print(2)"])
            assert False, "mismatched argv should fail"
        except guard.GuardError:
            pass
        # matching override is accepted
        r = guard.run_command(t, tmp, "ok", argv_override=["python3", "-c", "print(1)"])
        assert r["exit_code"] == 0

    # a failing command returns its real non-zero exit (guard does not judge)
    with tempfile.TemporaryDirectory() as tmp:
        t = _ticket(tmp, '{"commands": {"red": {"argv": ["python3","-c","import sys; sys.exit(1)"], "expected_exit": 1, "timeout": 30}}}')
        r = guard.run_command(t, tmp, "red")
        assert r["exit_code"] == 1 and r["expected_exit"] == 1, r

    # timeout is killed and reported with cleanup_required
    with tempfile.TemporaryDirectory() as tmp:
        t = _ticket(tmp, '{"commands": {"slow": {"argv": ["python3","-c","import time; time.sleep(10)"], "expected_exit": 0, "timeout": 1}}}')
        r = guard.run_command(t, tmp, "slow")
        assert r["timed_out"] is True and r["cleanup_required"] is True, r

    # cwd outside the boundary is refused
    with tempfile.TemporaryDirectory() as tmp:
        t = _ticket(tmp, '{"commands": {"esc": {"argv": ["python3","-c","print(1)"], "expected_exit": 0, "timeout": 30, "cwd": "/"}}}')
        try:
            guard.run_command(t, tmp, "esc")
            assert False, "out-of-boundary cwd should fail"
        except guard.GuardError:
            pass


def check_write_tests():
    with tempfile.TemporaryDirectory() as tmp:
        inside = str(Path(tmp) / "state.md")
        # ordinary write inside the boundary is allowed
        ok, _ = guard.check_write(inside, "Stage: TDD\nall good", tmp, tmp)
        assert ok is True
        # secret content is blocked
        ok, reason = guard.check_write(inside, "token=ghp_" + "a" * 30, tmp, tmp)
        assert ok is False and "secret" in reason
        # out-of-boundary path is blocked
        ok, reason = guard.check_write("/etc/passwd", "x", tmp, tmp)
        assert ok is False and "boundary" in reason


def out_file_tests():
    import json
    with tempfile.TemporaryDirectory() as tmp:
        t = _ticket(tmp, '{"commands": {"ok": {"argv": ["python3","-c","print(1)"], "expected_exit": 0, "timeout": 30}}}')
        out = str(Path(tmp) / "result.json")
        rc = guard.main(["run", "--ticket", t, "--repo", tmp, "--id", "ok", "--out", out])
        assert rc == 0
        # the durable file exists and holds the real result, independent of stdout
        payload = json.loads(Path(out).read_text(encoding="utf-8"))
        assert payload["exit_code"] == 0 and payload["id"] == "ok", payload


def main():
    guard._selftest()
    run_command_tests()
    check_write_tests()
    out_file_tests()
    print("test_guard: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
