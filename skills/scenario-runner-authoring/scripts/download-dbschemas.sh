#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 OUTPUT_ROOT [SCHEMA_ARTIFACT ...]" >&2
  exit 2
fi

for command_name in curl zstd tar awk sed find; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done

declare -a db_mapping=(
  "cis_schema,cis_db"
  "data1_schema,data1_db"
  "data2_schema,data2_db"
  "hadoop_schema,hadoop_db"
  "ls_schema,ls_db"
  "main_schema,main_db"
  "promocode_schema,promocode_db"
)

output_root="$1"
shift
requested=("$@")
mkdir -p "$output_root"
output_root="$(cd "$output_root" && pwd)"
temp_root="$(mktemp -d "${TMPDIR:-/tmp}/scenario-dbschemas.XXXXXX")"
trap 'rm -rf "$temp_root"' EXIT

for requested_artifact in ${requested[*]-}; do
  known=false
  for mapping in "${db_mapping[@]}"; do
    [[ "${mapping%%,*}" == "$requested_artifact" ]] && known=true
  done
  if [[ "$known" == false ]]; then
    echo "Unknown schema artifact: $requested_artifact" >&2
    exit 2
  fi
done

for mapping in "${db_mapping[@]}"; do
  IFS=',' read -r artifact db_folder <<< "$mapping"
  if [[ ${#requested[@]} -gt 0 && " ${requested[*]} " != *" $artifact "* ]]; then
    continue
  fi

  cluster_name="${artifact%%_*}"
  base_url="https://nexus3.mgo.com/repository/maven-releases/com/vudu/director2-databases/$artifact"
  version="$(curl -fsSL "$base_url/maven-metadata.xml" | awk -F '>' '$1 == "latest" {sub(/<.*/, "", $2); print $2; exit}' RS='<')"
  if [[ -z "$version" ]]; then
    echo "No latest version found for $artifact" >&2
    exit 1
  fi

  archive="$temp_root/$artifact.zst"
  extract_dir="$temp_root/$artifact"
  mkdir -p "$extract_dir"
  echo "Downloading $artifact $version" >&2
  curl -fsSL "$base_url/$version/$artifact-$version.zst" --output "$archive"
  zstd -dc "$archive" | tar -xf - -C "$extract_dir"

  dump_file="$(find "$extract_dir" -type f -name "${artifact}_dump.sql" -print -quit)"
  create_user="$(find "$extract_dir" -type f -name "create_user_${cluster_name}.sql" -print -quit)"
  user_grants="$(find "$extract_dir" -type f -name "user_grants_${cluster_name}.sql" -print -quit)"
  if [[ -z "$dump_file" || -z "$create_user" || -z "$user_grants" ]]; then
    echo "Archive for $artifact is missing its dump, user, or grants SQL" >&2
    exit 1
  fi

  destination_dir="$output_root/$db_folder/sql"
  destination="$destination_dir/$artifact.sql"
  mkdir -p "$destination_dir"
  {
    echo "SET SESSION FOREIGN_KEY_CHECKS=0;"
    echo "SET sql_mode = '';"
    sed '/DELIMITER/d' "$dump_file" "$create_user" "$user_grants"
  } > "$destination"

  json_destination="${destination//\\/\\\\}"
  json_destination="${json_destination//\"/\\\"}"
  printf '{"artifact":"%s","version":"%s","path":"%s"}\n' \
    "$artifact" "$version" "$json_destination"
done
