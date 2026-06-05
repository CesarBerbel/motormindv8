#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-}"
APP_DIR="${APP_DIR:-/var/www/motormind/current}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Execute como root ou com sudo."
  exit 1
fi

if [ -z "$DOMAIN" ]; then
  echo "Uso: sudo bash deploy/scripts/install_system_services.sh seudominio.com"
  exit 1
fi

cp "$APP_DIR/deploy/systemd/motormind.service" /etc/systemd/system/motormind.service
sed "s/SEU_DOMINIO/$DOMAIN/g" "$APP_DIR/deploy/nginx/motormind.conf" > /etc/nginx/sites-available/motormind.conf
ln -sf /etc/nginx/sites-available/motormind.conf /etc/nginx/sites-enabled/motormind.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl daemon-reload
systemctl enable motormind
systemctl restart motormind
systemctl reload nginx

cat <<MSG
Servicos instalados.
Acesse: http://$DOMAIN
Para HTTPS, instale um certificado SSL pelo painel da Hostinger ou via certbot se disponivel no servidor.
MSG
