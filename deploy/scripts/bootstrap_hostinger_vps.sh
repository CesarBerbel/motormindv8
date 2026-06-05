#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-motormind}"
APP_DIR="${APP_DIR:-/var/www/motormind/current}"
LOG_DIR="${LOG_DIR:-/var/log/motormind}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Execute como root ou com sudo: sudo bash deploy/scripts/bootstrap_hostinger_vps.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip build-essential nginx sqlite3 git unzip curl nodejs npm

if ! id "$APP_USER" >/dev/null 2>&1; then
  adduser --system --group --home /var/www/motormind "$APP_USER"
fi

mkdir -p "$APP_DIR" "$LOG_DIR"
chown -R "$APP_USER:www-data" /var/www/motormind "$LOG_DIR"
chmod 775 "$LOG_DIR"

cat <<MSG
Bootstrap concluido.
Proximos passos:
1. Envie o ZIP do projeto para a VPS.
2. Descompacte em $APP_DIR.
3. Copie .env.production.example para .env e ajuste dominio, SECRET_KEY e email.
4. Rode: sudo bash deploy/scripts/install_or_update_release.sh
MSG
