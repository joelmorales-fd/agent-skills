#!/usr/bin/env python3
"""Set DIRECTOR_DEPLOY_VERSION, DEPLOY_TYPE, and DB_DEPLOY_TYPE in environments.env.

Run from docker-director2/configurations/:
  ./set-config.py --director-version local --services router,CIS --db-deploy-type router,CIS
"""
import argparse
import os

ENV_FILE = "environments.env"
ALWAYS_ON = ["kafka", "redis"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--director-version", required=True, choices=["local", "latest"])
    parser.add_argument("--services", required=True, help="CSV, e.g. router,CIS — kafka,redis always appended")
    parser.add_argument("--db-deploy-type", required=True, help="AWS, or a CSV of services needing local DBs")
    args = parser.parse_args()

    if not os.path.exists(ENV_FILE):
        raise SystemExit(f"{ENV_FILE} not found — run from docker-director2/configurations/")

    with open(ENV_FILE) as f:
        lines = f.readlines()

    services = [s.strip() for s in args.services.split(",") if s.strip()]
    deploy_type = ",".join(services + ALWAYS_ON)

    updates = {
        "DIRECTOR_DEPLOY_VERSION": args.director_version,
        "DEPLOY_TYPE": deploy_type,
        "DB_DEPLOY_TYPE": args.db_deploy_type,
        "UPDATE_DATABASES": "No",
    }
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0] if "=" in line else None
        if key in updates:
            lines[i] = f"{key}={updates[key]}\n"
            seen.add(key)
    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}\n")

    os.replace(ENV_FILE, ENV_FILE + ".bak")
    with open(ENV_FILE, "w") as f:
        f.writelines(lines)

    for key, value in updates.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
