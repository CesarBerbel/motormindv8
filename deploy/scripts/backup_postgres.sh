#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/motormind/current}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/motormind}"
KEEP_DAYS="${KEEP_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

if [ ! -f "$APP_DIR/.env" ]; then
  echo "Arquivo .env nao encontrado em $APP_DIR/.env"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$APP_DIR/.env"
set +a

if [ "${DB_ENGINE:-}" != "django.db.backends.postgresql" ]; then
  echo "DB_ENGINE nao esta configurado para PostgreSQL. Use backup_sqlite.sh para SQLite."
  exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

export PGPASSWORD="$DB_PASSWORD"
pg_dump \
  --host="${DB_HOST:-127.0.0.1}" \
  --port="${DB_PORT:-5432}" \
  --username="$DB_USER" \
  --format=custom \
  --file="$BACKUP_DIR/motormind_postgres_$TIMESTAMP.dump" \
  "$DB_NAME"

tar -czf "$BACKUP_DIR/motormind_media_$TIMESTAMP.tar.gz" -C "$APP_DIR" media || true
find "$BACKUP_DIR" -type f -name 'motormind_postgres_*.dump' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -type f -name 'motormind_media_*.tar.gz' -mtime +"$KEEP_DAYS" -delete

cat <<MSG
Backup PostgreSQL concluido:
$BACKUP_DIR/motormind_postgres_$TIMESTAMP.dump
$BACKUP_DIR/motormind_media_$TIMESTAMP.tar.gz
MSG
