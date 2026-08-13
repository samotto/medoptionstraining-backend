#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set."
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "Usage: ./scripts/restore_db.sh backups/medoptionstraining-backup-file.sql"
  exit 1
fi

backup_file="$1"

if [[ ! -f "$backup_file" ]]; then
  echo "Backup file not found: $backup_file"
  exit 1
fi

psql "$DATABASE_URL" < "$backup_file"

echo "Restore complete from: $backup_file"
