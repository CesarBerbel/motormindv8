from django.contrib.auth.models import Permission

from .models import EmployeeRole


PROJECT_APP_LABELS = (
    'accounts',
    'audit',
    'ai_assistant',
    'communications',
    'core',
    'operations',
    'stock',
    'website',
)

TECHNICAL_AREA_ROLES = {
    EmployeeRole.ADM,
    EmployeeRole.TECNICO,
}

FULL_MECHANIC_QUEUE_ROLES = {
    EmployeeRole.ADM,
}


def get_project_permission_labels():
    """Return every application-level permission managed by MotorMind."""
    return list(
        Permission.objects
        .filter(content_type__app_label__in=PROJECT_APP_LABELS)
        .order_by('content_type__app_label', 'codename')
        .values_list('content_type__app_label', 'codename')
    )


def format_permission_label(permission_tuple):
    app_label, codename = permission_tuple
    return f'{app_label}.{codename}'


def get_administrative_permission_labels():
    """
    Administrative users should have the same in-app permissions as a
    superuser, but must not receive Django admin access through is_staff.
    """
    return [format_permission_label(permission) for permission in get_project_permission_labels()]


def can_access_technical_area(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    return bool(user.is_superuser or getattr(user, 'role', None) in TECHNICAL_AREA_ROLES)


def has_full_mechanic_queue_access(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    return bool(user.is_superuser or getattr(user, 'role', None) in FULL_MECHANIC_QUEUE_ROLES)
