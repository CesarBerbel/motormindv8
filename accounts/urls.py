from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import EmailAuthenticationForm
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=EmailAuthenticationForm,
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('funcionarios/', views.EmployeeListView.as_view(), name='employee_list'),
    path('funcionarios/autocomplete/', views.EmployeeAutocompleteView.as_view(), name='employee_autocomplete'),
    path('funcionarios/novo/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('funcionarios/<int:pk>/editar/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    path('funcionarios/<int:pk>/excluir/', views.EmployeeDeleteView.as_view(), name='employee_delete'),
]
