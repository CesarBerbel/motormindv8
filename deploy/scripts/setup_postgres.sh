#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${DB_NAME:-motormind}"
DB_USER="${DB_USER:-motormind}"
DB_PASSWORD="${DB_PASSWORD:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Execute como root ou com sudo: sudo DB_PASSWORD='senha-forte' bash deploy/scripts/setup_postgres.sh"
  exit 1
fi

if [ -z "$DB_PASSWORD" ]; then
  echo "Informe DB_PASSWORD. Exemplo: sudo DB_PASSWORD='senha-forte' bash deploy/scripts/setup_postgres.sh"
  exit 1
fi

apt-get update
apt-get install -y postgresql postgresql-contrib libpq-dev
systemctl enable postgresql
systemctl start postgresql

sudo -u postgres psql <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
      CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD';
   ELSE
      ALTER ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD';
   END IF;
END
\$\$;
SQL

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
fi

sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

cat <<MSG
PostgreSQL preparado.
Atualize o .env do MotorMind com:
DB_ENGINE=django.db.backends.postgresql
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=5432

Depois rode:
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart motormind
MSG
