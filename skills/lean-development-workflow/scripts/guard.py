#!/usr/bin/env python3
"""The lean-development-workflow guard.

Two jobs, nothing else (see docs: details/guard.md):

  run          run an approved command from commands.md by EXACT argv match,
               without a shell, with a timeout, and return its real result.
  check-write  allow an ordinary write; block one that stores a secret or falls
               outside the ticket/repo boundary.

The guard never interprets a result, decides a stage, judges code, or writes
state.md. No audit journal, lease, or receipts.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

MAX_OUTPUT = 256 * 1024  # bytes per stream; larger is truncated, not stored raw

# Coarse secret net — refuse rather than store these. Not a vault.
SECRET_PATTERNS = [
    re.compile(p) for p in (
        r"AKIA[0-9A-Z]{16}",                              # AWS access key id
        r"ghp_[A-Za-z0-9]{20,}",                          # GitHub token
        r"xox[baprs]-[A-Za-z0-9-]{10,}",                  # Slack token
        r"AIza[0-9A-Za-z_\-]{20,}",                       # Google API key
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",            # private key block
        r"(?i)authorization:\s*bearer\s+\S+",             # bearer header
        r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+",
    )
]


def find_secret(text):
    """Return the first secret-shaped match in text, or None."""
    if not isinstance(text, str):
        return None
    for pattern in SECRET_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


def within(path, roots):
    """True if the resolved path is inside one of the resolved roots."""
    target = Path(path).resolve(strict=False)
    for root in roots:
        root = Path(root).resolve(strict=False)
        if target == root or root in target.parents:
            return True
    return False


def load_commands(ticket_dir):
    """Read the authoritative approved-command JSON block from commands.md.

    commands.md must contain exactly one fenced ```json block whose object has a
    top-level "commands" map: {id: {argv:[...], expected_exit:int, timeout:int,
    cwd?:str}}.
    """
    path = Path(ticket_dir) / "commands.md"
    if not path.is_file():
        raise GuardError("commands.md not found in %s" % ticket_dir)
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if len(blocks) != 1:
        raise GuardError("commands.md must contain exactly one ```json block (found %d)" % len(blocks))
    try:
        data = json.loads(blocks[0])
    except (ValueError, json.JSONDecodeError) as exc:
        raise GuardError("commands.md json block is invalid: %s" % exc)
    commands = data.get("commands") if isinstance(data, dict) else None
    if not isinstance(commands, dict):
        raise GuardError("commands.md json block needs a 'commands' object")
    return commands


class GuardError(Exception):
    pass


def run_command(ticket_dir, repo_root, command_id, argv_override=None, now=time.time):
    """Run one approved command and return the real result as a dict."""
    commands = load_commands(ticket_dir)
    entry = commands.get(command_id)
    if not isinstance(entry, dict):
        raise GuardError("no approved command with id %r" % command_id)
    argv = entry.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise GuardError("approved command %r has an invalid argv" % command_id)
    if argv_override is not None and list(argv_override) != argv:
        raise GuardError("requested argv does not exactly match the approved entry %r" % command_id)
    secret = find_secret(" ".join(argv))
    if secret:
        raise GuardError("refusing to run: command argv contains a secret-shaped value")

    cwd = entry.get("cwd") or repo_root or ticket_dir
    roots = [r for r in (ticket_dir, repo_root) if r]
    if roots and not within(cwd, roots):
        raise GuardError("command cwd %s is outside the ticket/repo boundary" % cwd)

    timeout = entry.get("timeout")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        timeout = 120
    expected_exit = entry.get("expected_exit")

    start = now()
    timed_out = False
    try:
        proc = subprocess.Popen(
            argv, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        raise GuardError("could not start command: %s" % exc)
    try:
        out, err = proc.communicate(timeout=timeout)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        out, err = proc.communicate()
        exit_code = None
    duration = round(now() - start, 3)

    return {
        "id": command_id,
        "argv": argv,
        "cwd": str(cwd),
        "exit_code": exit_code,
        "expected_exit": expected_exit,
        "timed_out": timed_out,
        "cleanup_required": timed_out,
        "duration_seconds": duration,
        "stdout": _clean_output(out),
        "stderr": _clean_output(err),
    }


def _clean_output(raw):
    """Decode, cap size, and redact secret-shaped values from real output."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    truncated = False
    if len(text.encode("utf-8")) > MAX_OUTPUT:
        text = text.encode("utf-8")[:MAX_OUTPUT].decode("utf-8", "ignore")
        truncated = True
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    if truncated:
        text += "\n[...truncated by guard: output exceeded %d bytes...]" % MAX_OUTPUT
    return text


def check_write(path, content, ticket_dir, repo_root):
    """Return (allowed, reason). Blocks secret-bearing or out-of-boundary writes."""
    roots = [r for r in (ticket_dir, repo_root) if r]
    if roots and not within(path, roots):
        return False, "write target %s is outside the ticket/repo boundary" % path
    secret = find_secret(content)
    if secret:
        return False, "write blocked: content contains a secret-shaped value"
    return True, "ok"


# --- CLI ---------------------------------------------------------------------

def _maybe_write_out(out_path, payload):
    """Write the result JSON to a durable file so a long/large run's result is
    not lost if the caller drops or caps the stdout tail."""
    if not out_path:
        return
    try:
        Path(out_path).write_text(payload + "\n", encoding="utf-8")
        sys.stderr.write("guard: result written to %s\n" % out_path)
    except OSError as exc:
        sys.stderr.write("guard: could not write --out %s: %s\n" % (out_path, exc))


def _cmd_run(args):
    try:
        result = run_command(
            args.ticket, args.repo, args.id,
            argv_override=(args.argv if args.argv else None),
        )
    except GuardError as exc:
        payload = json.dumps({"guard_error": str(exc)})
        _maybe_write_out(args.out, payload)
        print(payload)
        return 2
    payload = json.dumps(result, indent=2)
    # Durable copy first — a 30-minute build's stdout can be dropped/capped by the
    # caller, but the file survives so the lead reads the result itself. The
    # process does everything; the human is not in this loop.
    _maybe_write_out(args.out, payload)
    print(payload)
    # Exit 0 means "the guard ran it"; the real exit_code is in the payload for
    # the lead to interpret. The guard never decides pass/fail.
    return 0


def _cmd_check_write(args):
    content = Path(args.file).read_text(encoding="utf-8", errors="replace") if args.file else sys.stdin.read()
    allowed, reason = check_write(args.path, content, args.ticket, args.repo)
    if allowed:
        return 0
    sys.stderr.write("BLOCKED: %s\n" % reason)
    return 2


def _cmd_selftest(_args):
    _selftest()
    print("guard selftest: OK")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="lean-development-workflow guard")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run an approved command by id")
    p_run.add_argument("--ticket", required=True)
    p_run.add_argument("--repo", default=None)
    p_run.add_argument("--id", required=True)
    p_run.add_argument("--out", default=None,
                       help="also write the result JSON here (durable for long/large runs)")
    p_run.add_argument("argv", nargs="*", help="optional: exact argv override (must match)")
    p_run.set_defaults(func=_cmd_run)

    p_cw = sub.add_parser("check-write", help="allow/block a write (exit 0/2)")
    p_cw.add_argument("--path", required=True)
    p_cw.add_argument("--ticket", required=True)
    p_cw.add_argument("--repo", default=None)
    p_cw.add_argument("--file", default=None, help="read content from file (else stdin)")
    p_cw.set_defaults(func=_cmd_check_write)

    p_st = sub.add_parser("selftest", help="run the built-in assertions")
    p_st.set_defaults(func=_cmd_selftest)

    args = parser.parse_args(argv)
    return args.func(args)


def _selftest():
    """Minimal assertions — the smallest thing that fails if the logic breaks."""
    assert find_secret("Authorization: Bearer abc123def") is not None
    assert find_secret("password = hunter2") is not None
    assert find_secret("just normal text") is None
    assert within("/a/b/c", ["/a/b"]) is True
    assert within("/a/b", ["/a/b"]) is True
    assert within("/a/x", ["/a/b"]) is False
    red = _clean_output(b"tok password=abc\nline2")
    assert "[REDACTED]" in red and "line2" in red
    big = _clean_output(b"x" * (MAX_OUTPUT + 10))
    assert "truncated by guard" in big


if __name__ == "__main__":
    sys.exit(main())
