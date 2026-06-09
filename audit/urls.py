from django.urls import path

from . import views

urlpatterns = [
    path('auditoria/autocomplete/', views.AuditLogAutocompleteView.as_view(), name='audit_autocomplete'),
    path('auditoria/', views.AuditLogListView.as_view(), name='audit_list'),
]
