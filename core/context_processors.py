from django.conf import settings


def pwa_settings(request):
    return {
        'pwa_enabled': bool(getattr(settings, 'PWA_ENABLED', False)),
        'pwa_debug_mode': bool(getattr(settings, 'DEBUG', False)),
    }
