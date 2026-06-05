# PostgreSQL em produção

O MotorMind v39 mantém SQLite para desenvolvimento/local, mas o banco recomendado para produção é PostgreSQL.

## 1. Instalar e preparar o PostgreSQL na VPS

Execute como `root` ou com `sudo`:

```bash
cd /var/www/motormind/current
sudo DB_PASSWORD='troque-por-uma-senha-forte' bash deploy/scripts/setup_postgres.sh
```

O script instala PostgreSQL, cria o usuário `motormind` e cria o banco `motormind` quando eles ainda não existem.

Para customizar nome do banco ou usuário:

```bash
sudo DB_NAME='motormind_prod' DB_USER='motormind_app' DB_PASSWORD='troque-por-uma-senha-forte' bash deploy/scripts/setup_postgres.sh
```

## 2. Configurar `.env`

No servidor, edite `/var/www/motormind/current/.env`:

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=motormind
DB_USER=motormind
DB_PASSWORD=troque-por-uma-senha-forte
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=60
DB_SSL_REQUIRE=False
```

## 3. Aplicar migrations

```bash
cd /var/www/motormind/current
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_roles
python manage.py collectstatic --noinput
sudo systemctl restart motormind
```

## 4. Migrar dados de SQLite existente para PostgreSQL

Antes de trocar o `.env` para PostgreSQL, gere um dump lógico usando o SQLite atual:

```bash
cd /var/www/motormind/current
source .venv/bin/activate
python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.Permission \
  --indent 2 > /tmp/motormind_sqlite_data.json
```

Depois configure o `.env` para PostgreSQL e rode:

```bash
python manage.py migrate
python manage.py loaddata /tmp/motormind_sqlite_data.json
python manage.py setup_roles
sudo systemctl restart motormind
```

Valide a aplicação antes de remover o `db.sqlite3` antigo.

## 5. Backup do PostgreSQL

```bash
sudo bash /var/www/motormind/current/deploy/scripts/backup_postgres.sh
```

Para restaurar um backup `.dump` em um banco vazio:

```bash
export PGPASSWORD='senha-do-banco'
pg_restore --host=127.0.0.1 --port=5432 --username=motormind --dbname=motormind --clean --if-exists /var/backups/motormind/motormind_postgres_YYYYMMDD_HHMMSS.dump
```
