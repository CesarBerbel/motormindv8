#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/motormind/current}"
APP_USER="${APP_USER:-motormind}"
SERVICE_NAME="${SERVICE_NAME:-motormind}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$APP_DIR"

if [ ! -f ".env" ]; then
  echo "Arquivo .env nao encontrado em $APP_DIR"
  echo "Copie .env.production.example para .env e ajuste antes de continuar."
  exit 1
fi

if [ ! -d ".venv" ]; then
  $PYTHON_BIN -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ -f "package.json" ]; then
  npm install
  npm run css:build
fi

python manage.py migrate --noinput
python manage.py setup_roles
python manage.py collectstatic --noinput
python manage.py check

mkdir -p media staticfiles
chown -R "$APP_USER:www-data" "$APP_DIR"
find "$APP_DIR/media" -type d -exec chmod 775 {} \; 2>/dev/null || true
find "$APP_DIR/staticfiles" -type d -exec chmod 775 {} \; 2>/dev/null || true

systemctl daemon-reload
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
  systemctl restart "$SERVICE_NAME"
else
  echo "Servico $SERVICE_NAME ainda nao instalado. Copie deploy/systemd/motormind.service para /etc/systemd/system/ e habilite."
fi
