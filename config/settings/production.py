"""Ambiente de producao.

Reforca defaults seguros mesmo que o .env os omita. Os valores continuam a
poder ser sobrepostos por variaveis de ambiente.
"""

import os

from .base import *  # noqa: F401,F403
from .base import env_bool

# Em producao o DEBUG deve estar sempre desligado.
DEBUG = False

# Cookies seguros por defeito (a aplicacao corre sob HTTPS via Nginx).
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', True)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', True)

# HSTS de um ano por defeito (so e enviado sob HTTPS).
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', str(365 * 24 * 60 * 60)))

# Aviso defensivo: ALLOWED_HOSTS nao deve ficar com os defaults locais.
if ALLOWED_HOSTS == ['127.0.0.1', 'localhost']:  # noqa: F405
    import warnings

    warnings.warn(
        'ALLOWED_HOSTS está com os valores de desenvolvimento em produção. '
        'Defina ALLOWED_HOSTS no .env.',
        RuntimeWarning,
    )
