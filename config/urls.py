from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('website.urls')),
    path('', include('core.urls')),
    path('', include('accounts.urls')),
    path('', include('communications.urls')),
    path('', include('stock.urls')),
    path('', include('operations.urls')),
    path('', include('ai_assistant.urls')),
    path('', include('audit.urls')),
    path('sentry-debug/', trigger_error),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
