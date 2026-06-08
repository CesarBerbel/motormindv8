"""Encriptacao transparente de campos sensiveis (ex.: chaves de API).

O valor e guardado cifrado na base de dados e devolvido em texto simples ao
codigo Python. A cifra usada e a Fernet (AES-128 em modo CBC + HMAC) da
biblioteca `cryptography`.

Gestao da chave:
- Se a variavel de ambiente FIELD_ENCRYPTION_KEY estiver definida, e usada
  diretamente (deve ser uma chave Fernet urlsafe base64 de 32 bytes, gerada
  com `Fernet.generate_key()`).
- Caso contrario, a chave e derivada da SECRET_KEY do projeto. Isto permite o
  funcionamento imediato em desenvolvimento, mas em producao deve definir-se
  uma FIELD_ENCRYPTION_KEY dedicada: assim a rotacao da SECRET_KEY nao torna
  os dados cifrados ilegiveis.

Compatibilidade com dados antigos: linhas que ainda contenham a chave em texto
simples (anteriores a esta alteracao) sao devolvidas tal como estao e passam a
ser cifradas no proximo `save()`.
"""

import base64
import binascii
import functools
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


@functools.lru_cache(maxsize=1)
def _build_fernet(key_material):
    return Fernet(key_material)


def get_fernet():
    raw = os.getenv('FIELD_ENCRYPTION_KEY', '').strip()
    if raw:
        key_material = raw.encode()
    else:
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key_material = base64.urlsafe_b64encode(digest)
    return _build_fernet(key_material)


class EncryptedTextField(models.TextField):
    """Campo de texto cifrado em repouso.

    Usa TextField (e nao CharField) porque o texto cifrado e bastante mais
    longo do que o valor original, pelo que nao faz sentido impor max_length.
    """

    def from_db_value(self, value, expression, connection):
        if value in (None, ''):
            return value
        try:
            return get_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, binascii.Error, ValueError):
            # Valor legado em texto simples ou nao decifravel: devolve tal como
            # esta. Sera cifrado no proximo save().
            return value

    def get_prep_value(self, value):
        if value in (None, ''):
            return value
        return get_fernet().encrypt(str(value).encode()).decode()
