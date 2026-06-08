from django.urls import path

from . import views

urlpatterns = [
    path('auditoria/', views.AuditLogListView.as_view(), name='audit_list'),
]
