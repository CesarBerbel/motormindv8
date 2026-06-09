from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from accounts.models import EmployeeRole
from accounts.permissions import get_administrative_permission_labels
from accounts.utils import ROLE_GROUP_NAMES, sync_user_role_group


PERMISSIONS_BY_ROLE = {
    EmployeeRole.ADM: [],  # preenchido dinamicamente com todas as permissões das apps do MotorMind
    EmployeeRole.ATENDENTE: [
        'ai_assistant.use_ai_assistant',
        'core.view_customer',
        'core.add_customer',
        'core.change_customer',
        'core.view_vehicle',
        'core.add_vehicle',
        'core.change_vehicle',
        'core.view_supplier',
        'core.view_category',
        'communications.view_messagelog',
        'communications.add_messagelog',
        'communications.view_messagetemplate',
        'stock.view_inventoryitem',
        'stock.view_stockmovement',
        'stock.view_purchaseorder',
        'operations.view_workorder',
        'operations.add_workorder',
        'operations.change_workorder',
        'operations.view_workorderstatustransition',
        'operations.view_workorderapprovalbudget',
        'operations.view_workorderapprovalbudgetitem',
        'operations.view_workorderapprovalaudit',
        'operations.view_vehiclecheckin',
        'operations.add_vehiclecheckin',
        'operations.change_vehiclecheckin',
        'operations.view_servicecategory',
        'operations.add_servicecategory',
        'operations.change_servicecategory',
        'operations.view_service',
        'operations.add_service',
        'operations.change_service',
        'operations.view_servicecombo',
        'operations.add_servicecombo',
        'operations.change_servicecombo',
    ],
    EmployeeRole.TECNICO: [
        'ai_assistant.use_ai_assistant',
        'core.view_customer',
        'core.view_vehicle',
        'core.view_supplier',
        'core.view_category',
        'stock.view_inventoryitem',
        'stock.view_stockmovement',
        'stock.add_stockmovement',
        'stock.view_purchaseorder',
        'stock.add_purchaseorder',
        'stock.change_purchaseorder',
        'operations.view_workorder',
        'operations.change_workorder',
        'operations.view_workorderstatustransition',
        'operations.view_workorderapprovalbudget',
        'operations.view_workorderapprovalbudgetitem',
        'operations.view_workorderapprovalaudit',
        'operations.view_vehiclecheckin',
        'operations.add_vehiclecheckin',
        'operations.change_vehiclecheckin',
        'operations.view_servicecategory',
        'operations.view_service',
        'operations.view_servicecombo',
    ],
    EmployeeRole.FINANCEIRO: [
        'ai_assistant.use_ai_assistant',
        'core.view_customer',
        'core.change_customer',
        'core.view_vehicle',
        'core.view_supplier',
        'core.change_supplier',
        'core.view_category',
        'communications.view_messagelog',
        'communications.view_messagetemplate',
        'stock.view_inventoryitem',
        'stock.view_stockmovement',
        'stock.view_purchaseorder',
        'operations.view_workorder',
        'operations.view_workorderstatustransition',
        'operations.view_workorderapprovalbudget',
        'operations.view_workorderapprovalbudgetitem',
        'operations.view_workorderapprovalaudit',
        'operations.view_vehiclecheckin',
        'operations.view_servicecategory',
        'operations.view_service',
        'operations.view_servicecombo',
    ],
    EmployeeRole.ESTOQUE: [
        'ai_assistant.use_ai_assistant',
        'core.view_supplier',
        'core.add_supplier',
        'core.change_supplier',
        'core.view_category',
        'core.add_category',
        'core.change_category',
        'communications.view_messagelog',
        'communications.add_messagelog',
        'communications.view_messagetemplate',
        'stock.view_stockcategory',
        'stock.add_stockcategory',
        'stock.change_stockcategory',
        'stock.delete_stockcategory',
        'stock.view_brand',
        'stock.add_brand',
        'stock.change_brand',
        'stock.delete_brand',
        'stock.view_unitofmeasure',
        'stock.view_inventoryitem',
        'stock.add_inventoryitem',
        'stock.change_inventoryitem',
        'stock.delete_inventoryitem',
        'stock.view_stockmovement',
        'stock.add_stockmovement',
        'stock.view_purchaseorder',
        'stock.add_purchaseorder',
        'stock.change_purchaseorder',
        'stock.delete_purchaseorder',
        'stock.view_purchaseorderitem',
        'stock.add_purchaseorderitem',
        'stock.change_purchaseorderitem',
        'stock.delete_purchaseorderitem',
        'operations.view_workorder',
        'operations.view_workorderstatustransition',
        'operations.view_workorderapprovalbudget',
        'operations.view_workorderapprovalbudgetitem',
        'operations.view_workorderapprovalaudit',
        'operations.view_vehiclecheckin',
        'operations.view_servicecategory',
        'operations.add_servicecategory',
        'operations.change_servicecategory',
        'operations.view_service',
        'operations.add_service',
        'operations.change_service',
        'operations.view_servicecombo',
        'operations.add_servicecombo',
        'operations.change_servicecombo',
    ],
}


class Command(BaseCommand):
    help = 'Cria grupos e permissões padrão dos perfis de funcionários.'

    def handle(self, *args, **options):
        for role, configured_permission_labels in PERMISSIONS_BY_ROLE.items():
            group_name = ROLE_GROUP_NAMES[role]
            group, _ = Group.objects.get_or_create(name=group_name)
            group.permissions.clear()

            permission_labels = (
                get_administrative_permission_labels()
                if role == EmployeeRole.ADM
                else configured_permission_labels
            )

            for permission_label in permission_labels:
                app_label, codename = permission_label.split('.')
                permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
                group.permissions.add(permission)

            self.stdout.write(self.style.SUCCESS(f'Grupo configurado: {group_name}'))

        User = get_user_model()
        for user in User.objects.filter(is_superuser=False):
            sync_user_role_group(user)

        self.stdout.write(self.style.SUCCESS('Permissões configuradas com sucesso.'))
