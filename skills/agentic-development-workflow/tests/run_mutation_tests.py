#!/usr/bin/env python3
"""Run curated workflow safety mutations against temporary source copies."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "adw_core.py"
CLI = ROOT / "scripts" / "adw.py"
RECEIPTS = ROOT / "scripts" / "adw_receipts.py"
TESTS = ROOT / "tests" / "test_adw_core.py"
CASES = ROOT / "tests" / "mutation_cases.json"


def run_tests(test_file, selectors=()):
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(test_file), "-v"] + list(selectors),
        cwd=str(test_file.parents[1]),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def load_cases():
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    if payload.get("schema") != 1 or not isinstance(payload.get("cases"), list):
        raise ValueError("mutation case catalog must use schema 1 and contain cases")
    required = {"id", "invariant", "search", "replacement", "tests"}
    allowed = required | {"source"}
    for case in payload["cases"]:
        if not required <= set(case) <= allowed or not all(isinstance(case[name], str) and case[name] for name in required - {"tests"}):
            raise ValueError("mutation case fields are invalid")
        if case.get("source", "adw_core.py") not in {"adw_core.py", "adw_receipts.py"}:
            raise ValueError("mutation case source is invalid")
        if not isinstance(case["tests"], list) or not case["tests"] or not all(isinstance(value, str) and value for value in case["tests"]):
            raise ValueError("mutation case tests must be non-empty strings")
    return payload["cases"]


def run_case(case):
    with tempfile.TemporaryDirectory(prefix="adw-mutation-") as temporary:
        root = Path(temporary)
        scripts = root / "scripts"
        tests = root / "tests"
        scripts.mkdir()
        tests.mkdir()
        core = scripts / SOURCE.name
        cli = scripts / CLI.name
        receipts = scripts / RECEIPTS.name
        test_file = tests / TESTS.name
        shutil.copy2(SOURCE, core)
        shutil.copy2(CLI, cli)
        shutil.copy2(RECEIPTS, receipts)
        shutil.copy2(TESTS, test_file)
        shutil.copytree(ROOT / "assets", root / "assets")
        source = scripts / case.get("source", SOURCE.name)
        control = run_tests(test_file, case["tests"])
        if control.returncode != 0:
            return {
                "id": case["id"],
                "invariant": case["invariant"],
                "status": "invalid_case",
                "detail": "selected tests fail before mutation",
                "output_tail": control.stdout.splitlines()[-12:],
            }
        content = source.read_text(encoding="utf-8")
        occurrences = content.count(case["search"])
        if occurrences != 1:
            return {
                "id": case["id"],
                "invariant": case["invariant"],
                "status": "invalid_case",
                "detail": "expected one mutation target, found %s" % occurrences,
            }
        source.write_text(content.replace(case["search"], case["replacement"], 1), encoding="utf-8")
        completed = run_tests(test_file, case["tests"])
        return {
            "id": case["id"],
            "invariant": case["invariant"],
            "status": "survived" if completed.returncode == 0 else "killed",
            "tests": case["tests"],
            "output_tail": completed.stdout.splitlines()[-12:],
        }


def main():
    baseline = run_tests(TESTS)
    result = {
        "schema": 1,
        "scope": "agentic-development-workflow/scripts/adw_core.py and adw_receipts.py",
        "baseline": "pass" if baseline.returncode == 0 else "fail",
        "tooling": "configured",
        "cases": [],
    }
    if baseline.returncode != 0:
        result["baseline_output_tail"] = baseline.stdout.splitlines()[-20:]
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    result["cases"] = [run_case(case) for case in load_cases()]
    result["outcome"] = "useful_signal" if all(case["status"] == "killed" for case in result["cases"]) else "real_gap"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["outcome"] == "useful_signal" else 1


if __name__ == "__main__":
    sys.exit(main())
