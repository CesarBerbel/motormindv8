"""Integracao opcional com o Sentry para monitorizacao de erros e performance.

A inicializacao e totalmente controlada por variaveis de ambiente e e um no-op
quando SENTRY_DSN nao esta definida (ex.: desenvolvimento e testes). Se o pacote
``sentry-sdk`` nao estiver instalado mas existir uma DSN, emite-se apenas um aviso
para nao impedir o arranque da aplicacao.

Variaveis de ambiente:
    SENTRY_DSN                    DSN do projeto Sentry. Vazia => monitorizacao desligada.
    SENTRY_ENVIRONMENT            Nome do ambiente (default: valor de DJANGO_ENV ou 'production').
    SENTRY_RELEASE               Identificador da release (opcional).
    SENTRY_TRACES_SAMPLE_RATE    Amostragem de tracing (0.0 a 1.0, default 0.0).
    SENTRY_PROFILES_SAMPLE_RATE  Amostragem de profiling (0.0 a 1.0, default 0.0).
    SENTRY_SEND_DEFAULT_PII      Enviar dados pessoais por defeito (default False).
"""

import logging
import os

logger = logging.getLogger('config.monitoring')


def _env_float(name, default):
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning('Valor invalido para %s=%r; a usar %s.', name, raw, default)
        return default


def init_sentry():
    """Inicializa o Sentry se houver DSN configurada. Devolve True se ativado."""
    dsn = os.getenv('SENTRY_DSN', '').strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        logger.warning(
            'SENTRY_DSN definida mas o pacote sentry-sdk nao esta instalado; '
            'monitorizacao desativada. Instale com: pip install sentry-sdk.'
        )
        return False

    environment = (
        os.getenv('SENTRY_ENVIRONMENT')
        or os.getenv('DJANGO_ENV')
        or 'production'
    )

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=os.getenv('SENTRY_RELEASE') or None,
        integrations=[
            DjangoIntegration(),
            # Erros (logging.ERROR) viram eventos; nao duplicar breadcrumbs de INFO.
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=_env_float('SENTRY_TRACES_SAMPLE_RATE', 0.0),
        profiles_sample_rate=_env_float('SENTRY_PROFILES_SAMPLE_RATE', 0.0),
        send_default_pii=os.getenv('SENTRY_SEND_DEFAULT_PII', 'False').lower()
        in {'1', 'true', 'yes', 'on'},
    )
    logger.info('Sentry inicializado para o ambiente %s.', environment)
    return True
