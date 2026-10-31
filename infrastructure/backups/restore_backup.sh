#!/usr/bin/env bash
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "Usage: $0 <path-to-luxe_db_backup.sql.gz>"
  exit 1
fi
BACKUP_FILE="$1"
echo "Verifying archive integrity..."
gzip -t "$BACKUP_FILE"
echo "Restoring database into PostgreSQL..."
gunzip -c "$BACKUP_FILE" | psql "${DATABASE_URL}"
echo "Restore completed successfully."
