from django.urls import path

from . import views

urlpatterns = [
    path('configuracoes/mensagens/', views.MessageSettingsView.as_view(), name='message_settings'),
    path('mensagens/manual/', views.ManualMessageView.as_view(), name='message_manual'),
    path('mensagens/historico/', views.MessageHistoryView.as_view(), name='message_history'),
    path('mensagens/templates/', views.MessageTemplateListView.as_view(), name='message_template_list'),
    path('mensagens/templates/novo/', views.MessageTemplateCreateView.as_view(), name='message_template_create'),
    path('mensagens/templates/<int:pk>/editar/', views.MessageTemplateUpdateView.as_view(), name='message_template_update'),
    path('mensagens/templates/<int:pk>/excluir/', views.MessageTemplateDeleteView.as_view(), name='message_template_delete'),
]
