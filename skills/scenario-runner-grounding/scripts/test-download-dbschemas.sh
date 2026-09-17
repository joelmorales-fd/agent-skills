#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
mkdir -p "$work_dir/bin" "$work_dir/output"
printf '%s\n' 'CREATE TABLE studios (id BIGINT NOT NULL);' > "$work_dir/schema.sql"

cat > "$work_dir/bin/curl" <<'EOF'
#!/bin/bash
if [[ "$*" == *maven-metadata.xml* ]]; then
  printf '%s\n' '<metadata><versioning><latest>7.2.1</latest></versioning></metadata>'
  exit 0
fi
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "--output" ]]; then
    : > "$2"
    exit 0
  fi
  shift
done
exit 1
EOF
cat > "$work_dir/bin/zstd" <<'EOF'
#!/bin/bash
printf 'archive'
EOF
cat > "$work_dir/bin/tar" <<'EOF'
#!/bin/bash
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-C" ]]; then
    cat >/dev/null
    for artifact in cis_schema data1_schema data2_schema hadoop_schema ls_schema main_schema promocode_schema; do
      cp "$SCHEMA_FIXTURE" "$2/${artifact}_dump.sql"
      cluster="${artifact%%_*}"
      : > "$2/create_user_${cluster}.sql"
      : > "$2/user_grants_${cluster}.sql"
    done
    exit 0
  fi
  shift
done
exit 1
EOF
chmod +x "$work_dir/bin/"*

output="$(PATH="$work_dir/bin:$PATH" SCHEMA_FIXTURE="$work_dir/schema.sql" \
  bash "$script_dir/download-dbschemas.sh" "$work_dir/output")"

test -f "$work_dir/output/cis_db/sql/cis_schema.sql"
grep -q 'CREATE TABLE studios' "$work_dir/output/cis_db/sql/cis_schema.sql"
grep -q '"artifact":"cis_schema"' <<< "$output"
grep -q '"artifact":"main_schema"' <<< "$output"
grep -q '"version":"7.2.1"' <<< "$output"
test "$(grep -c '"artifact":"cis_schema"' <<< "$output")" -eq 1
test "$(grep -c '"artifact":' <<< "$output")" -eq 7

if PATH="$work_dir/bin:$PATH" bash "$script_dir/download-dbschemas.sh" \
  "$work_dir/output" unknown_schema >/dev/null 2>&1; then
  exit 1
fi
