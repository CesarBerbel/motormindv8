"""Utilitários de auditoria: IP do cliente, serialização e mascaramento."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

# Campos sensíveis cujo valor nunca deve ser gravado em claro na auditoria.
SENSITIVE_HINTS = ('password', 'senha', 'api_key', 'token', 'secret')


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def is_sensitive_field(name):
    name = (name or '').lower()
    return any(hint in name for hint in SENSITIVE_HINTS)


def serialize_value(value):
    """Converte um valor para algo serializável em JSON e legível."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return str(value)
