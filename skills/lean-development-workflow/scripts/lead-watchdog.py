#!/usr/bin/env python3
"""Lead watchdog for the lean development workflow.

An LLM lead cannot keep its own timer between turns: while it waits on a long
command it is not executing, so it can appear to "sleep" and stop making
progress. This watchdog is the external clock. It watches a ticket's `state.md`,
and when the run has gone quiet during an active stage it queues a short "validate
and continue" message into the lead's Codex session so the lead wakes, re-reads
`state.md`, and takes the next action.

It only *prompts* the lead. It never writes `state.md`, never decides a stage, and
never ends the run — so it stays inside the workflow rule that only the lead ends
the process. It exits by itself once the stage reaches COMPLETE or BLOCKED.

Wake channel: `codex queue --thread <id> --message <text>` — enqueues a wake message
for the lead's session. It must target the lead's own session (from CODEX_THREAD_ID),
or the message reaches the wrong thread. (`codex exec resume` is refused when the
session is open in an interactive TUI — "thread already has an active writer".)

The session to wake can be given with `--thread`, or discovered automatically: the
watchdog reads Codex's session index and picks the session that matches the ticket
by git branch or session name, so the lead can start it with only `--ticket`.

Example:
    python3 lead-watchdog.py \
        --ticket /path/to/AVOD-548-Testing \
        --interval 300 --idle 600
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Stage reached when the lead is done or has handed back to a human.
TERMINAL_STAGES = {"COMPLETE", "BLOCKED"}

# `Stage: TDD`, `**Stage:** TDD`, `Stage = TDD`, etc.
STAGE_RE = re.compile(r"stage\s*[:=]\s*\**\s*([A-Za-z]+)", re.IGNORECASE)

DEFAULT_MESSAGE = (
    "Work continuously on the active ticket. Do not end your turn after a status "
    "update, assignment, command launch, agent message, or intermediate result.\n"
    "\n"
    "Repeat this loop in the same turn:\n"
    "1. Read state.md.\n"
    "2. Perform the next required action.\n"
    "3. If you delegated work, wait for the result.\n"
    "4. Inspect the real diff and command output yourself.\n"
    "5. Update state.md, including an append-only History entry.\n"
    "6. Immediately continue to the next workflow action.\n"
    "\n"
    "Do not ask me to continue. Do not give a final response while an action is "
    "pending. Do not treat an assignment as completion.\n"
    "\n"
    "You may stop only when:\n"
    "- I must approve or clarify a specification decision,\n"
    "- a genuine blocker remains after safe alternatives and diagnosis are exhausted, or\n"
    "- the ticket is COMPLETE.\n"
    "\n"
    "For TDD, JUDGE, and MUTATION, proceed autonomously all the way through the next "
    "stage. If a test or review fails, route it immediately to the required correction "
    "and continue the loop."
)

# Codex keeps its session store under CODEX_HOME (default ~/.codex).
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
SESSION_INDEX = CODEX_HOME / "session_index.jsonl"
SESSIONS_DIR = CODEX_HOME / "sessions"

# A Jira-style ticket key such as `AVOD-548`.
TICKET_KEY_RE = re.compile(r"[A-Za-z]+-\d+")
# The git branch recorded in the first record of a session file.
BRANCH_RE = re.compile(r'"branch"\s*:\s*"([^"]+)"')


def ticket_tokens(ticket_dir: Path) -> set[str]:
    """Lowercased strings that identify this ticket (its dir name and ticket key)."""
    name = ticket_dir.name
    tokens = {name.lower()}
    key = TICKET_KEY_RE.search(name)
    if key:
        tokens.add(key.group(0).lower())
    return tokens


def session_index_entries() -> list[dict]:
    """Session index rows (id, thread_name, updated_at), newest first."""
    entries: list[dict] = []
    try:
        for line in SESSION_INDEX.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("id"):
                entries.append(row)
    except OSError:
        return []
    entries.sort(key=lambda row: row.get("updated_at", ""), reverse=True)
    return entries


def session_branch(session_id: str) -> str | None:
    """The git branch recorded in the session's own file, if it can be read."""
    try:
        matches = sorted(SESSIONS_DIR.rglob(f"*{session_id}*.jsonl"))
    except OSError:
        return None
    if not matches:
        return None
    try:
        with matches[0].open(encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
    except OSError:
        return None
    found = BRANCH_RE.search(first)
    return found.group(1) if found else None


def discover_thread(ticket_dir: Path) -> tuple[str | None, str]:
    """Find the Codex session for this ticket.

    Prefer a session whose git branch names the ticket, then one whose session
    name does. Fall back to the newest session, flagged as unconfirmed. Returns
    the session id (or None) and a short reason for logging.
    """
    tokens = ticket_tokens(ticket_dir)
    entries = session_index_entries()
    for row in entries:
        branch = session_branch(row["id"])
        if branch and any(token in branch.lower() for token in tokens):
            return row["id"], f"branch {branch!r}"
    for row in entries:
        name = (row.get("thread_name") or "").lower()
        if name and any(token in name for token in tokens):
            return row["id"], f"session name {row.get('thread_name')!r}"
    if entries:
        return entries[0]["id"], "newest session (UNCONFIRMED match)"
    return None, "no sessions found"


def read_stage(state_path: Path) -> str | None:
    """Return the current stage from state.md, or None if it can't be read."""
    try:
        text = state_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = STAGE_RE.search(text)
    return match.group(1).upper() if match else None


def state_signature(state_path: Path) -> str:
    """A content fingerprint of state.md that changes only when the ticket does.

    The counter compares this between checks instead of reading a wall clock, so
    progress detection cannot drift by timezone or a mis-written timestamp.
    """
    try:
        return hashlib.sha256(state_path.read_bytes()).hexdigest()
    except OSError:
        return ""


def detect_runtime(explicit: "str | None") -> str:
    """Return 'codex' or 'claude'. An explicit choice wins; otherwise the session
    environment variable decides, the same signal the declaration hooks use
    (CLAUDE_CODE_SESSION_ID means Claude, CODEX_THREAD_ID means Codex). Defaults to
    Codex when neither is set.
    """
    if explicit and explicit != "auto":
        return explicit
    if os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude"
    if os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    return "codex"


def session_from_env(runtime: str) -> "str | None":
    """The lead's own session id from the runtime's environment variable."""
    var = "CLAUDE_CODE_SESSION_ID" if runtime == "claude" else "CODEX_THREAD_ID"
    return os.environ.get(var) or None


def nudge(runtime: str, cli: str, thread: str, message: str, log_path: Path) -> bool:
    """Send the wake message to the lead's session for the given runtime.

    Codex uses `codex queue`, which enqueues a message and returns at once, so it
    does not fight the interactive window's writer. Claude has no queue equivalent,
    so it uses `claude --resume <id> --print`, which resumes the session and runs a
    full turn; that is launched detached so a long turn is not killed by a timeout.
    The Claude path is not yet verified against a session held open in a window — it
    may conflict or fork, and should be revisited after a runtime test. Waking works
    only when `thread` is the lead's own session.
    """
    if runtime == "claude":
        argv = [cli, "--resume", thread, "--print", message]
        try:
            handle = open(log_path, "a", buffering=1, encoding="utf-8")
            try:
                subprocess.Popen(argv, stdout=handle, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL)
            finally:
                handle.close()  # the child keeps its own dup'd fd
            return True
        except (OSError, subprocess.SubprocessError) as exc:
            log(f"nudge failed to launch: {exc}")
            return False
    try:
        result = subprocess.run(
            [cli, "queue", "--thread", thread, "--message", message],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"nudge failed to run: {exc}")
        return False
    if result.returncode != 0:
        log(f"nudge exit {result.returncode}: {result.stderr.strip() or result.stdout.strip()}")
        return False
    return True


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def pid_alive(pid: int) -> bool:
    """True if a process with this pid exists."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def running_pid(pid_path: Path) -> int | None:
    """The live watchdog pid recorded in pid_path, or None."""
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return pid if pid_alive(pid) else None


def daemonize(log_path: Path, pid_path: Path) -> None:
    """Detach into a background session and record the pid.

    A POSIX double fork plus setsid, because the sandbox blocks `nohup` (its nice
    call is denied) and `setsid` is not installed. The double fork detaches from the
    controlling terminal and the launching process group so the watchdog outlives the
    turn that started it. Output goes to log_path; the pid goes to pid_path so the
    lead can confirm it is running without process-listing tools.
    """
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, "rb", 0) as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    handle = open(log_path, "a", buffering=1, encoding="utf-8")
    os.dup2(handle.fileno(), sys.stdout.fileno())
    os.dup2(handle.fileno(), sys.stderr.fileno())
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Wake a stalled lead until COMPLETE/BLOCKED.")
    parser.add_argument("--ticket", required=True, help="Ticket directory containing state.md")
    parser.add_argument("--thread", default=None,
                        help="Session UUID or exact name. Defaults to the lead's own "
                             "session from CLAUDE_CODE_SESSION_ID or CODEX_THREAD_ID; "
                             "branch discovery is only a last resort (Codex only).")
    parser.add_argument("--runtime", choices=["auto", "codex", "claude"], default="auto",
                        help="Which agent runtime to wake. 'auto' detects it from the "
                             "session environment variable (default).")
    parser.add_argument("--interval", type=int, default=180, help="Seconds between checks (default 180)")
    parser.add_argument("--idle", type=int, default=540,
                        help="Seconds of no progress before a nudge (default = 540)")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="Wake message to send")
    parser.add_argument("--codex", default="codex", help="Path to the codex CLI (default 'codex')")
    parser.add_argument("--claude", default="claude", help="Path to the claude CLI (default 'claude')")
    parser.add_argument("--once", action="store_true", help="Run one check and exit (for testing)")
    parser.add_argument("--detach", action="store_true",
                        help="Run in the background as a daemon and record a pid file")
    args = parser.parse_args()

    # Use the values the launch actually passed, so the log shows the real cadence and
    # you can see whether the chosen --interval/--idle were used.
    interval = args.interval
    idle = args.idle if args.idle is not None else args.interval
    ticket_dir = Path(args.ticket).expanduser().resolve()
    state_path = ticket_dir / "state.md"
    pid_path = ticket_dir / ".watchdog.pid"

    if not state_path.exists():
        log(f"state.md not found at {state_path}")
        return 2

    existing = running_pid(pid_path)
    if existing is not None:
        log(f"watchdog already running for this ticket (pid {existing}); not starting another.")
        return 0

    if args.detach:
        daemonize(ticket_dir / ".watchdog.log", pid_path)

    # Detect the runtime (codex or claude) and take the lead's own session id from
    # its environment variable, preferring that over branch discovery.
    runtime = detect_runtime(args.runtime)
    cli = args.claude if runtime == "claude" else args.codex
    thread = args.thread or session_from_env(runtime)
    if thread:
        env_var = "CLAUDE_CODE_SESSION_ID" if runtime == "claude" else "CODEX_THREAD_ID"
        thread_desc = f"{thread} (from {'--thread' if args.thread else env_var})"
    else:
        thread_desc = "auto-discover"
    # Turn the idle budget into a count of unchanged checks (never a wall-clock read).
    stall_limit = max(1, math.ceil(idle / interval))
    resume_log = ticket_dir / ".watchdog-resume.log"
    prev_sig = state_signature(state_path)
    stalls = 0
    log(f"watching {state_path} (runtime={runtime}, thread={thread_desc}, "
        f"interval={interval}s, nudge after {stall_limit} unchanged check(s))")

    try:
        while True:
            # Self-heal to exactly one watchdog per ticket: if a newer daemon has taken
            # over the pid file, step aside; if the file went missing, reclaim it.
            if args.detach:
                owner = running_pid(pid_path)
                if owner is None:
                    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
                elif owner != os.getpid():
                    log(f"superseded by watchdog pid {owner}; exiting.")
                    return 0

            stage = read_stage(state_path)
            if stage in TERMINAL_STAGES:
                log(f"stage is {stage}; nothing to drive. Exiting.")
                return 0

            sig = state_signature(state_path)
            if sig != prev_sig:
                prev_sig = sig
                stalls = 0
            else:
                stalls += 1

            if stage is None:
                log("could not read a stage from state.md; will retry.")
            elif stalls >= stall_limit:
                if thread is None:
                    if runtime == "codex":
                        thread, why = discover_thread(ticket_dir)
                        if thread is None:
                            log(f"no session to nudge yet ({why}); will retry.")
                        else:
                            log(f"discovered session {thread} via {why}.")
                    else:
                        log("no session id for claude; set CLAUDE_CODE_SESSION_ID or "
                            "--thread. Will retry.")
                if thread is not None:
                    log(f"stage {stage}, unchanged for {stalls} check(s) >= {stall_limit} — nudging lead.")
                    if nudge(runtime, cli, thread, args.message, resume_log):
                        log("nudge sent.")
                        stalls = 0
            else:
                log(f"stage {stage}, unchanged for {stalls}/{stall_limit} check(s) — no nudge.")

            if args.once:
                return 0
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                log("interrupted; exiting.")
                return 0
    finally:
        # Only remove the pid file if it still names us, so a superseded watchdog
        # never deletes the newer one's file.
        if args.detach and running_pid(pid_path) == os.getpid():
            pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
