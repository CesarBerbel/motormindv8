from .models import SiteSettings


def site_settings(request):
    """Disponibiliza as configurações do site público em todos os templates."""
    return {'site': SiteSettings.get_solo()}
