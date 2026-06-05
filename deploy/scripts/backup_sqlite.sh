#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/motormind/current}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/motormind}"
DB_PATH="${DB_PATH:-$APP_DIR/db.sqlite3}"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
  echo "Banco SQLite nao encontrado em $DB_PATH"
  exit 1
fi

sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/db_$STAMP.sqlite3'"
if [ -d "$APP_DIR/media" ]; then
  tar -czf "$BACKUP_DIR/media_$STAMP.tar.gz" -C "$APP_DIR" media
fi

find "$BACKUP_DIR" -type f -mtime +14 -delete

echo "Backup criado em $BACKUP_DIR com timestamp $STAMP"
