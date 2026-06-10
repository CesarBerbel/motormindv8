"""Ambiente de testes.

Acelera a suite (hasher rapido, base em memoria) e isola o cache. Selecionado
com DJANGO_ENV=testing.
"""

from .base import *  # noqa: F401,F403

DEBUG = False

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'motormind-tests',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Mantém o PWA ativo nos testes automatizados, salvo override_settings.
PWA_ENABLED = env_bool('PWA_ENABLED', True)
