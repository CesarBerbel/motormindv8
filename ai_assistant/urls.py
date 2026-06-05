from django.urls import path

from . import views

urlpatterns = [
    path('configuracoes/ia/', views.AISettingsView.as_view(), name='ai_settings'),
    path('configuracoes/ia/testar/', views.AITestConnectionView.as_view(), name='ai_test_connection'),
    path('ia/assistir-texto/', views.AITextAssistView.as_view(), name='ai_text_assist'),
]
