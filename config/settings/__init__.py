"""Selecao do modulo de definicoes por ambiente.

O ambiente e escolhido pela variavel DJANGO_ENV:
    development (default) | production | testing

Para retrocompatibilidade, se DJANGO_ENV nao estiver definida, o ambiente e
inferido a partir de DEBUG (development quando DEBUG=True, caso contrario
production). Assim, DJANGO_SETTINGS_MODULE continua a ser 'config.settings'.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env antes de decidir o ambiente para que DJANGO_ENV/DEBUG possam
# vir do ficheiro.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')


def _truthy(value):
    return str(value).lower() in {'1', 'true', 'yes', 'on'}


_env = os.getenv('DJANGO_ENV', '').strip().lower()
if not _env:
    _env = 'development' if _truthy(os.getenv('DEBUG', 'True')) else 'production'

if _env in {'prod', 'production'}:
    from .production import *  # noqa: F401,F403
elif _env in {'test', 'testing'}:
    from .testing import *  # noqa: F401,F403
else:
    from .development import *  # noqa: F401,F403
