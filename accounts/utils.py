from django.contrib.auth.models import Group

from .models import EmployeeRole

ROLE_GROUP_NAMES = {
    EmployeeRole.ADM: 'Administrativo',
    EmployeeRole.ATENDENTE: 'Atendente',
    EmployeeRole.TECNICO: 'Técnico',
    EmployeeRole.FINANCEIRO: 'Financeiro',
    EmployeeRole.ESTOQUE: 'Estoque',
}


def sync_user_role_group(user):
    if user.is_superuser:
        return

    role_group_names = set(ROLE_GROUP_NAMES.values())
    user.groups.remove(*Group.objects.filter(name__in=role_group_names))

    group_name = ROLE_GROUP_NAMES.get(user.role)
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
