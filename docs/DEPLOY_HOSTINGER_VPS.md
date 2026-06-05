# Deploy do MotorMind em VPS Hostinger

Este guia prepara o MotorMind para rodar em uma VPS Linux com Nginx, Gunicorn, systemd, ambiente `.env`, arquivos estaticos coletados e backup do SQLite.

A estrutura esperada no servidor e:

```txt
/var/www/motormind/current
├── .env
├── .venv/
├── manage.py
├── db.sqlite3
├── media/
└── staticfiles/
```

## 1. Apontar dominio

No DNS do dominio, aponte o registro `A` para o IP publico da VPS.

Exemplo:

```txt
seudominio.com      A      IP_DA_VPS
www.seudominio.com  A      IP_DA_VPS
```

## 2. Preparar a VPS

Acesse por SSH:

```bash
ssh root@IP_DA_VPS
```

Envie o ZIP do projeto para a VPS ou clone o repositorio. Depois, dentro da pasta do projeto, rode:

```bash
sudo bash deploy/scripts/bootstrap_hostinger_vps.sh
```

Esse script instala os pacotes basicos:

- Python 3;
- venv/pip;
- Nginx;
- Node/npm;
- SQLite;
- ferramentas de build.

## 3. Instalar o projeto

Crie a pasta e descompacte o projeto:

```bash
sudo mkdir -p /var/www/motormind/current
sudo unzip motormind_django_tailwind_daisyui_fixed_v37_deploy_hostinger.zip -d /var/www/motormind/current
sudo chown -R motormind:www-data /var/www/motormind
```

Entre na pasta:

```bash
cd /var/www/motormind/current
```

Copie o arquivo de ambiente:

```bash
sudo cp .env.production.example .env
sudo nano .env
```

Ajuste principalmente:

```env
SECRET_KEY=gere-uma-chave-grande-e-unica
DEBUG=False
ALLOWED_HOSTS=seudominio.com,www.seudominio.com,IP_DA_VPS
CSRF_TRUSTED_ORIGINS=https://seudominio.com,https://www.seudominio.com
DB_NAME=/var/www/motormind/current/db.sqlite3
```

Para gerar uma chave segura:

```bash
python3 - <<'PY'
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
PY
```

## 4. Instalar dependencias, migrar e coletar estaticos

```bash
sudo bash deploy/scripts/install_or_update_release.sh
```

Esse script executa:

```bash
python -m venv .venv
pip install -r requirements.txt
npm install
npm run css:build
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py collectstatic --noinput
python manage.py check
```

## 5. Instalar systemd e Nginx

Com o dominio ja apontado, rode:

```bash
sudo bash deploy/scripts/install_system_services.sh seudominio.com
```

O script:

- instala `/etc/systemd/system/motormind.service`;
- instala `/etc/nginx/sites-available/motormind.conf`;
- habilita o site no Nginx;
- reinicia Gunicorn;
- recarrega Nginx.

## 6. Ativar HTTPS

Use o SSL da propria Hostinger, quando disponivel no painel, ou emita certificado no servidor se estiver usando Certbot.

Depois do HTTPS ativo, mantenha no `.env`:

```env
SECURE_PROXY_SSL_HEADER=True
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CSRF_TRUSTED_ORIGINS=https://seudominio.com,https://www.seudominio.com
```

Se ainda estiver testando sem HTTPS, deixe temporariamente:

```env
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

## 7. Criar usuario administrador

```bash
cd /var/www/motormind/current
sudo -u motormind .venv/bin/python manage.py createsuperuser
```

## 8. Popular catalogo inicial opcional

```bash
cd /var/www/motormind/current
sudo -u motormind .venv/bin/python manage.py seed_realistic_catalog
```

## 9. Atualizar uma nova versao

Antes de atualizar, faca backup:

```bash
sudo bash /var/www/motormind/current/deploy/scripts/backup_sqlite.sh
```

Depois substitua os arquivos do projeto, preservando:

- `.env`;
- `db.sqlite3`;
- `media/`.

Rode novamente:

```bash
cd /var/www/motormind/current
sudo bash deploy/scripts/install_or_update_release.sh
```

## 10. Comandos uteis

Status do app:

```bash
sudo systemctl status motormind
```

Logs do Gunicorn:

```bash
sudo journalctl -u motormind -f
sudo tail -f /var/log/motormind/error.log
```

Testar Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Testar saude da aplicacao:

```bash
curl http://127.0.0.1:8001/healthz/
```

Reiniciar aplicacao:

```bash
sudo systemctl restart motormind
```

## 11. Checklist de producao

Antes de liberar para uso real:

- `DEBUG=False`;
- `SECRET_KEY` unica e forte;
- `ALLOWED_HOSTS` com dominio e IP corretos;
- `CSRF_TRUSTED_ORIGINS` com `https://`;
- SMTP configurado;
- SSL ativo;
- backup testado;
- superusuario criado;
- `python manage.py check --deploy` revisado;
- permissao de escrita em `media/` e no banco SQLite, se estiver usando SQLite.
