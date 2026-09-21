#!/usr/bin/env python3
"""Prove the watchdog can launch itself as a background daemon and be verified.

The lead runs inside the Codex sandbox, which blocks `nohup` (its nice call is
denied) and `pgrep` (no process listing). This test checks the launch path that
does work: the watchdog's own `--detach` mode (a POSIX double fork) plus a pid
file the lead can read to confirm the daemon is alive without process tools.

Run: python3 tests/test_watchdog_launch.py
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "lead-watchdog.py"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def main() -> int:
    assert SCRIPT.is_file(), f"watchdog not found at {SCRIPT}"

    with tempfile.TemporaryDirectory() as tmp:
        ticket = Path(tmp)
        # A minimal ticket: an active stage and an old timestamp so it looks quiet.
        (ticket / "state.md").write_text(
            "- **Stage:** TDD\n\n## History\n2020-01-01 00:00 — TDD — seed\n",
            encoding="utf-8",
        )
        pid_path = ticket / ".watchdog.pid"
        log_path = ticket / ".watchdog.log"

        # Launch detached. --codex /bin/echo makes any nudge a harmless echo, and a
        # huge idle means it never actually nudges during the test.
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--ticket", str(ticket), "--detach",
             "--codex", "/bin/echo", "--interval", "2", "--idle", "999999"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"launcher exited {result.returncode}: {result.stderr}"

        # The daemon writes its pid file shortly after detaching.
        pid = None
        for _ in range(50):
            if pid_path.exists():
                pid = int(pid_path.read_text(encoding="utf-8").strip())
                break
            time.sleep(0.1)
        assert pid is not None, "daemon never wrote its pid file"
        assert pid_alive(pid), f"daemon pid {pid} is not alive"

        # It should have detached from the launcher (different pid) and logged that
        # it is watching the ticket.
        for _ in range(50):
            if log_path.exists() and "watching" in log_path.read_text(encoding="utf-8"):
                break
            time.sleep(0.1)
        log_text = log_path.read_text(encoding="utf-8")
        assert "watching" in log_text, f"daemon did not log a watch line:\n{log_text}"

        # A second launch must not start a rival daemon.
        second = subprocess.run(
            [sys.executable, str(SCRIPT), "--ticket", str(ticket), "--detach",
             "--codex", "/bin/echo", "--interval", "2", "--idle", "999999"],
            capture_output=True, text=True, timeout=30,
        )
        assert "already running" in (second.stdout + second.stderr), \
            f"second launch did not detect the running daemon:\n{second.stdout}{second.stderr}"
        assert int(pid_path.read_text(encoding="utf-8").strip()) == pid, "pid file changed"

        # Stop the daemon before the temp ticket is torn down so no orphan lingers.
        try:
            os.kill(pid, 15)
        except OSError:
            pass
        for _ in range(50):
            if not pid_alive(pid):
                break
            time.sleep(0.1)
        assert not pid_alive(pid), f"daemon pid {pid} did not stop on signal"

    print("test_watchdog_launch: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
