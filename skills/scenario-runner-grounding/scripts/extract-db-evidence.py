#!/usr/bin/env python3
"""Emit bounded schema (DDL) evidence as JSON."""

import argparse
import json
import re
import sys
from pathlib import Path


def extract_ddl(path: Path, table: str, max_lines: int) -> dict:
    lines = path.read_text(errors="replace").splitlines()
    start = re.compile(rf"^CREATE TABLE `{re.escape(table)}` \(")
    for index, line in enumerate(lines):
        if not start.match(line):
            continue
        block = []
        for candidate in lines[index : index + max_lines + 1]:
            block.append(candidate)
            if candidate.startswith(")") and candidate.endswith(";"):
                return {"schema": str(path), "table": table, "ddl": "\n".join(block)}
        raise ValueError(f"DDL for {table} exceeds --max-lines={max_lines}")
    raise ValueError(f"CREATE TABLE `{table}` not found in {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    ddl = subparsers.add_parser("ddl")
    ddl.add_argument("schema", type=Path)
    ddl.add_argument("table")
    ddl.add_argument("--max-lines", type=int, default=400)

    args = parser.parse_args()
    try:
        result = extract_ddl(args.schema, args.table, args.max_lines)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
