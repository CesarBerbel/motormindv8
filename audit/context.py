"""Contexto da requisição atual por thread.

Permite que os signals de alteração de modelos (que não recebem a request)
saibam qual o utilizador, IP e caminho responsáveis pela alteração.
"""

import threading

_state = threading.local()


def set_current_request(request):
    _state.request = request


def get_current_request():
    return getattr(_state, 'request', None)


def clear_current_request():
    if hasattr(_state, 'request'):
        del _state.request
