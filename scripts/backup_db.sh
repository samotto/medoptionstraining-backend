#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set."
  exit 1
fi

mkdir -p backups
timestamp="$(date +%Y%m%d-%H%M%S)"
outfile="backups/medoptionstraining-backup-${timestamp}.sql"

pg_dump "$DATABASE_URL" > "$outfile"

echo "Backup complete: $outfile"
