from django.db import migrations


SERVICE = 'service'
COMBO = 'combo'
PART = 'part'


def _matches_parent(child, parent):
    if child.parent_id or child.tipo != PART:
        return False
    origem_tipo = (child.origem_tipo or '').lower()
    if parent.tipo == SERVICE and 'serv' not in origem_tipo:
        return False
    if parent.tipo == COMBO and 'combo' not in origem_tipo:
        return False

    child_names = {value for value in [child.origem_nome, child.origem_codigo] if value}
    parent_names = {value for value in [parent.nome, parent.codigo, parent.origem_nome, parent.origem_codigo] if value}
    return bool(child_names & parent_names)


def repair_existing_budget_item_hierarchy(apps, schema_editor):
    WorkOrderApprovalBudgetItem = apps.get_model('operations', 'WorkOrderApprovalBudgetItem')
    budget_ids = (
        WorkOrderApprovalBudgetItem.objects
        .filter(parent__isnull=True, tipo=PART)
        .exclude(origem_tipo='')
        .values_list('orcamento_id', flat=True)
        .distinct()
    )
    for budget_id in budget_ids.iterator():
        items = list(
            WorkOrderApprovalBudgetItem.objects
            .filter(orcamento_id=budget_id)
            .order_by('hierarquia_ordem', 'pk')
        )
        parents = [item for item in items if item.parent_id is None and item.tipo in {SERVICE, COMBO}]
        if not parents:
            continue

        to_update = []
        child_index_by_parent = {}
        for item in items:
            if item.parent_id or item.tipo != PART:
                continue
            for parent in parents:
                if not _matches_parent(item, parent):
                    continue
                child_index = child_index_by_parent.get(parent.pk, 0) + 1
                child_index_by_parent[parent.pk] = child_index
                item.parent_id = parent.pk
                item.hierarquia_ordem = (parent.hierarquia_ordem or 0) + child_index
                to_update.append(item)
                break
        if to_update:
            WorkOrderApprovalBudgetItem.objects.bulk_update(to_update, ['parent', 'hierarquia_ordem'])


class Migration(migrations.Migration):

    dependencies = [
        ('operations', '0016_service_default_part_required_budget_hierarchy'),
    ]

    operations = [
        migrations.RunPython(repair_existing_budget_item_hierarchy, migrations.RunPython.noop),
    ]
