# Fase de deploy

Arquivos desta pasta:

```txt
deploy/
├── nginx/motormind.conf
├── systemd/motormind.service
└── scripts/
    ├── bootstrap_hostinger_vps.sh
    ├── install_or_update_release.sh
    ├── install_system_services.sh
    └── backup_sqlite.sh
```

Guia completo:

```txt
docs/DEPLOY_HOSTINGER_VPS.md
```


## PostgreSQL em produção

O MotorMind v39 recomenda PostgreSQL para produção. Para preparar o banco na VPS:

```bash
cd /var/www/motormind/current
sudo DB_PASSWORD='troque-por-uma-senha-forte' bash deploy/scripts/setup_postgres.sh
```

Depois ajuste o `.env` conforme `.env.production.example`, rode `python manage.py migrate` e reinicie o serviço. O guia completo está em `docs/POSTGRESQL_PRODUCAO.md`.
