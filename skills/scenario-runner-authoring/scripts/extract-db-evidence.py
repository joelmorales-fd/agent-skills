#!/usr/bin/env python3
"""Emit bounded schema or harness-fixture evidence as JSON."""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
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


def extract_fixture(path: Path, table: str, ids: set[str], max_rows: int) -> dict:
    rows = []
    root = ET.parse(path).getroot()
    for case in root.findall("case"):
        input_node = case.find("input")
        if input_node is None or input_node.findtext("table") != table:
            continue
        for row in input_node.findall("row"):
            values = {child.tag: child.text or "" for child in row}
            if ids and not ids.intersection(values.values()):
                continue
            rows.append(values)
            if len(rows) > max_rows:
                raise ValueError(
                    f"more than --max-rows={max_rows} matched; add IDs or lower the scope"
                )
    if not rows:
        raise ValueError(f"no matching rows for {table} in {path}")
    return {"fixture": str(path), "table": table, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    ddl = subparsers.add_parser("ddl")
    ddl.add_argument("schema", type=Path)
    ddl.add_argument("table")
    ddl.add_argument("--max-lines", type=int, default=400)

    fixture = subparsers.add_parser("fixture")
    fixture.add_argument("fixture", type=Path)
    fixture.add_argument("table")
    fixture.add_argument("--id", action="append", default=[])
    fixture.add_argument("--max-rows", type=int, default=20)

    args = parser.parse_args()
    try:
        if args.command == "ddl":
            result = extract_ddl(args.schema, args.table, args.max_lines)
        else:
            result = extract_fixture(
                args.fixture, args.table, set(args.id), args.max_rows
            )
    except (OSError, ET.ParseError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
