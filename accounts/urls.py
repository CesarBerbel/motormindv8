from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import StyledPasswordChangeForm, StyledPasswordResetForm, StyledSetPasswordForm
from . import views

urlpatterns = [
    path('login/', views.SecureLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('senha/alterar/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change_form.html',
        form_class=StyledPasswordChangeForm,
        success_url=reverse_lazy('password_change_done'),
    ), name='password_change'),
    path('senha/alterada/', auth_views.PasswordChangeDoneView.as_view(
        template_name='registration/password_change_done.html',
    ), name='password_change_done'),

    path('senha/redefinir/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        form_class=StyledPasswordResetForm,
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('senha/redefinir/enviado/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('senha/redefinir/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        form_class=StyledSetPasswordForm,
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('senha/redefinir/concluido/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),

    path('funcionarios/', views.EmployeeListView.as_view(), name='employee_list'),
    path('funcionarios/autocomplete/', views.EmployeeAutocompleteView.as_view(), name='employee_autocomplete'),
    path('funcionarios/novo/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('funcionarios/<int:pk>/editar/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    path('funcionarios/<int:pk>/excluir/', views.EmployeeDeleteView.as_view(), name='employee_delete'),
]
