"""Ambiente de desenvolvimento.

Mantem os defaults permissivos da base (DEBUG=True, cookies sem secure,
email para a consola). Tudo continua a poder ser ajustado pelo .env.
"""

from .base import *  # noqa: F401,F403

# Desligado por padrão no runserver para não prender CSS/JS antigos em cache.
PWA_ENABLED = env_bool('PWA_ENABLED', False)
