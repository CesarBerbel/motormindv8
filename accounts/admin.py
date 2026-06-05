from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import UserAdminChangeForm, UserAdminCreationForm
from .models import User
from .utils import sync_user_role_group


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    model = User

    list_display = ('email', 'nome_razao_social', 'role', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser', 'tipo_pessoa')
    search_fields = ('email', 'nome_razao_social', 'documento', 'whatsapp')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissões', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dados cadastrais', {
            'fields': (
                'tipo_pessoa',
                'nome_razao_social',
                'documento',
                'data_nascimento_fundacao',
                'whatsapp',
                'cep',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'aceita_marketing',
            )
        }),
        ('Datas importantes', {'fields': ('last_login', 'date_joined', 'criado_em', 'atualizado_em')}),
    )

    readonly_fields = ('criado_em', 'atualizado_em')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        sync_user_role_group(obj)

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'nome_razao_social',
                'role',
                'tipo_pessoa',
                'password1',
                'password2',
                'is_active',
                'is_staff',
                'is_superuser',
            ),
        }),
    )
