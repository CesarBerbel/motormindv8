"""Ambiente de desenvolvimento.

Mantem os defaults permissivos da base (DEBUG=True, cookies sem secure,
email para a consola). Tudo continua a poder ser ajustado pelo .env.
"""

from .base import *  # noqa: F401,F403
