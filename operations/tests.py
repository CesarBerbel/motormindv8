from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.urls import reverse
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from accounts.models import EmployeeRole, User
from core.models import Customer, PessoaTipo, Vehicle
from operations.models import (
    CustomerVehicleAccessToken,
    Service,
    ServiceCombo,
    ServiceComboItem,
    ServiceDefaultPart,
    WorkOrder,
    WorkOrderApprovalBudget,
    WorkOrderApprovalBudgetItem,
    WorkOrderApprovalDecision,
    WorkOrderApprovalItemType,
    WorkOrderApprovalStatus,
    WorkOrderComboItem,
    WorkOrderPartItem,
    WorkOrderServiceItem,
    WorkOrderStatus,
)
from operations.services.work_order_pricing import (
    inventory_margin_percent,
    inventory_margin_value,
    inventory_sale_price,
)
from stock.models import InventoryItem, InventoryItemType, StockCategory, UnitOfMeasure


class _FakeItem:
    def __init__(self, preco_venda, preco_custo, tipo=InventoryItemType.PECA):
        self.preco_venda = preco_venda
        self.preco_custo = preco_custo
        self.tipo = tipo


class InventoryPricingTests(SimpleTestCase):
    def test_sale_price_uses_preco_venda_when_positive(self):
        item = _FakeItem(Decimal('100.00'), Decimal('60.00'))
        self.assertEqual(inventory_sale_price(item), Decimal('100.00'))

    def test_sale_price_falls_back_to_cost_when_venda_zero(self):
        item = _FakeItem(Decimal('0.00'), Decimal('60.00'))
        self.assertEqual(inventory_sale_price(item), Decimal('60.00'))

    def test_sale_price_falls_back_to_cost_when_venda_none(self):
        item = _FakeItem(None, Decimal('42.00'))
        self.assertEqual(inventory_sale_price(item), Decimal('42.00'))

    def test_margin_value(self):
        item = _FakeItem(Decimal('100.00'), Decimal('60.00'))
        self.assertEqual(inventory_margin_value(item), Decimal('40.00'))

    def test_margin_percent(self):
        item = _FakeItem(Decimal('100.00'), Decimal('60.00'))
        self.assertEqual(inventory_margin_percent(item), Decimal('40.00'))

    def test_margin_percent_zero_when_no_sale_price(self):
        item = _FakeItem(Decimal('0.00'), Decimal('0.00'))
        self.assertEqual(inventory_margin_percent(item), Decimal('0.00'))

    def test_supply_sale_price_is_zero_even_with_prices(self):
        item = _FakeItem(Decimal('100.00'), Decimal('60.00'), tipo=InventoryItemType.INSUMO)
        self.assertEqual(inventory_sale_price(item), Decimal('0.00'))


class WorkOrderStatusMachineTests(SimpleTestCase):
    def test_same_status_is_allowed(self):
        self.assertTrue(
            WorkOrderStatus.can_transition(WorkOrderStatus.ABERTA, WorkOrderStatus.ABERTA)
        )

    def test_allowed_transition(self):
        self.assertTrue(
            WorkOrderStatus.can_transition(WorkOrderStatus.ABERTA, WorkOrderStatus.DIAGNOSTICO)
        )

    def test_disallowed_transition(self):
        self.assertFalse(
            WorkOrderStatus.can_transition(WorkOrderStatus.ABERTA, WorkOrderStatus.ENTREGUE)
        )

    def test_terminal_status_has_no_next(self):
        self.assertEqual(WorkOrderStatus.next_statuses(WorkOrderStatus.ARQUIVADA), [])

    def test_cancelada_can_only_archive(self):
        self.assertEqual(
            WorkOrderStatus.next_statuses(WorkOrderStatus.CANCELADA),
            [WorkOrderStatus.ARQUIVADA],
        )


class WorkOrderFixtureMixin:
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            tipo_pessoa=PessoaTipo.FISICA,
            nome_razao_social='Cliente Teste',
            email='cliente.teste@example.com',
        )
        self.service = Service.objects.create(nome='Diagnóstico', valor=Decimal('100.00'))
        self.categoria = StockCategory.objects.create(nome='Filtros Ops Teste')
        self.unidade = UnitOfMeasure.objects.create(nome='Unidade OpsTeste', sigla='uot')
        self.item = InventoryItem.objects.create(
            nome='Filtro de ar',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('30.00'),
            preco_venda=Decimal('50.00'),
        )
        self.insumo = InventoryItem.objects.create(
            tipo=InventoryItemType.INSUMO,
            nome='Limpa contato',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('12.00'),
            preco_venda=Decimal('30.00'),
        )

    def _work_order(self, **kwargs):
        defaults = {
            'cliente': self.customer,
            'problema_relatado': 'Motor com ruído',
            'status': WorkOrderStatus.ABERTA,
        }
        defaults.update(kwargs)
        return WorkOrder.objects.create(**defaults)


class WorkOrderCodeTests(WorkOrderFixtureMixin, TestCase):
    def test_codigo_is_generated_on_creation(self):
        order = self._work_order()
        self.assertEqual(order.codigo, f'OS-{order.pk:05d}')


class WorkOrderItemTests(WorkOrderFixtureMixin, TestCase):
    def test_service_item_unit_price_defaults_to_service_value(self):
        order = self._work_order()
        line = WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        self.assertEqual(line.valor_unitario, Decimal('100.00'))

    def test_service_item_subtotal(self):
        order = self._work_order()
        line = WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=3)
        self.assertEqual(line.subtotal, Decimal('300.00'))

    def test_part_item_unit_price_defaults_to_sale_price(self):
        order = self._work_order()
        line = WorkOrderPartItem.objects.create(ordem_servico=order, item=self.item, quantidade=2)
        self.assertEqual(line.valor_unitario, Decimal('50.00'))
        self.assertEqual(line.subtotal, Decimal('100.00'))


class WorkOrderTotalsTests(WorkOrderFixtureMixin, TestCase):
    def test_subtotal_servicos(self):
        order = self._work_order()
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=2)
        self.assertEqual(order.subtotal_servicos, Decimal('200.00'))

    def test_subtotal_without_parts_or_combos_equals_services(self):
        order = self._work_order()
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=2)
        self.assertEqual(order.subtotal_combos, Decimal('0.00'))
        self.assertEqual(order.subtotal_pecas, Decimal('0.00'))
        self.assertEqual(order.subtotal, Decimal('200.00'))

    def test_valor_total_without_discount(self):
        order = self._work_order()
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=2)
        self.assertEqual(order.valor_desconto, Decimal('0.00'))
        self.assertEqual(order.valor_total, Decimal('200.00'))

    def test_valor_total_with_discount(self):
        order = self._work_order(desconto_percentual=Decimal('10.00'))
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=2)
        self.assertEqual(order.valor_desconto, Decimal('20.00'))
        self.assertEqual(order.valor_total, Decimal('180.00'))

    def test_subtotal_pecas_avulsas(self):
        order = self._work_order()
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.item, quantidade=3)
        self.assertEqual(order.subtotal_pecas_avulsas, Decimal('150.00'))

    def test_insumo_avulso_nao_soma_no_valor_da_os_mas_rastreia_custo(self):
        order = self._work_order()
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.item, quantidade=2)
        insumo_line = WorkOrderPartItem.objects.create(ordem_servico=order, item=self.insumo, quantidade=3)

        self.assertEqual(insumo_line.valor_unitario, Decimal('0.00'))
        self.assertEqual(insumo_line.subtotal, Decimal('0.00'))
        self.assertEqual(order.subtotal_pecas_avulsas, Decimal('100.00'))
        self.assertEqual(order.subtotal_pecas, Decimal('100.00'))
        self.assertEqual(order.valor_total, Decimal('100.00'))
        self.assertEqual(order.custo_insumos, Decimal('36.00'))

    def test_stock_requirements_preserve_insumo_as_internal_expense(self):
        order = self._work_order()
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.insumo, quantidade=2)

        requirement = order.get_stock_requirements()[0]

        self.assertTrue(requirement['is_internal_supply'])
        self.assertFalse(requirement['is_billable_to_customer'])
        self.assertEqual(requirement['subtotal'], Decimal('0.00'))
        self.assertEqual(requirement['custo_total'], Decimal('24.00'))

    def test_approval_budget_hides_insumo_from_customer_and_excludes_from_total(self):
        order = self._work_order()
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.item, quantidade=1)
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.insumo, quantidade=2)

        budget = WorkOrderApprovalBudget.create_from_work_order(order)

        self.assertEqual(budget.valor_total_snapshot, Decimal('50.00'))
        self.assertEqual(budget.total_itens, 2)
        self.assertEqual(budget.total_itens_cliente, 1)
        self.assertEqual(budget.total_itens_internos, 1)
        self.assertEqual(list(budget.customer_visible_items_ordered.values_list('nome', flat=True)), ['Filtro de ar'])
        internal_item = budget.internal_supply_items_ordered[0]
        self.assertEqual(internal_item.nome, 'Limpa contato')
        self.assertEqual(internal_item.subtotal, Decimal('0.00'))
        self.assertEqual(internal_item.display_tipo, 'Insumo interno')

    def test_partial_approval_keeps_internal_supply_hidden_but_approved_for_tracking(self):
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.item, quantidade=1)
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.insumo, quantidade=2)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)
        visible_item = budget.customer_visible_items_ordered[0]

        budget.apply_decision(
            WorkOrderApprovalDecision.APPROVE_PARTIAL,
            approved_item_ids=[visible_item.pk],
            responsible_name='Cliente Teste',
            document='12345678901',
        )
        budget.refresh_from_db()

        self.assertEqual(budget.status, WorkOrderApprovalStatus.PARTIALLY_APPROVED)
        self.assertTrue(budget.internal_supply_items_ordered[0].aprovado)
        self.assertEqual(order.valor_total, Decimal('50.00'))
        requirement = order.get_stock_requirements()[0]
        self.assertIn(requirement['item'].pk, {self.item.pk, self.insumo.pk})

    def test_service_default_parts_are_nested_under_service_budget_item(self):
        optional_item = InventoryItem.objects.create(
            nome='Aditivo opcional',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('10.00'),
            preco_venda=Decimal('30.00'),
        )
        ServiceDefaultPart.objects.create(service=self.service, item=self.item, quantidade=1, obrigatoria=True)
        ServiceDefaultPart.objects.create(service=self.service, item=optional_item, quantidade=1, obrigatoria=False)
        order = self._work_order()
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)

        budget = WorkOrderApprovalBudget.create_from_work_order(order)
        rows = list(budget.customer_visible_items_ordered)

        self.assertEqual([row.nome for row in rows], ['Diagnóstico', 'Aditivo opcional', 'Filtro de ar'])
        service_row = rows[0]
        optional_row = rows[1]
        mandatory_row = rows[2]
        self.assertIsNone(service_row.parent_id)
        self.assertEqual(optional_row.parent_id, service_row.pk)
        self.assertEqual(mandatory_row.parent_id, service_row.pk)
        self.assertFalse(optional_row.peca_obrigatoria)
        self.assertTrue(mandatory_row.peca_obrigatoria)
        self.assertEqual(budget.valor_total_snapshot, Decimal('180.00'))

    def test_partial_approval_is_blocked_for_single_service_without_parts(self):
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)
        service_row = budget.customer_visible_items_ordered[0]

        self.assertFalse(budget.allows_partial_approval)
        self.assertIn('apenas um serviço sem peças', budget.partial_approval_block_reason())
        with self.assertRaisesMessage(ValueError, 'apenas um serviço'):
            budget.apply_decision(
                WorkOrderApprovalDecision.APPROVE_PARTIAL,
                approved_item_ids=[service_row.pk],
                responsible_name='Cliente Teste',
                document='12345678901',
            )

        budget.refresh_from_db()
        service_row.refresh_from_db()
        self.assertEqual(budget.status, WorkOrderApprovalStatus.PENDING)
        self.assertIsNone(service_row.aprovado)

    def test_partial_approval_is_blocked_for_single_service_with_only_mandatory_parts(self):
        ServiceDefaultPart.objects.create(service=self.service, item=self.item, quantidade=1, obrigatoria=True)
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)
        rows = list(budget.customer_visible_items_ordered)

        self.assertFalse(budget.allows_partial_approval)
        self.assertIn('apenas um serviço com peças obrigatórias', budget.partial_approval_block_reason())
        with self.assertRaisesMessage(ValueError, 'apenas um serviço'):
            budget.apply_decision(
                WorkOrderApprovalDecision.APPROVE_PARTIAL,
                approved_item_ids=[row.pk for row in rows],
                responsible_name='Cliente Teste',
                document='12345678901',
            )

        budget.refresh_from_db()
        self.assertEqual(budget.status, WorkOrderApprovalStatus.PENDING)
        self.assertFalse(budget.itens.exclude(aprovado__isnull=True).exists())


    def test_partial_approval_is_blocked_for_legacy_parentless_mandatory_service_parts(self):
        ServiceDefaultPart.objects.create(service=self.service, item=self.item, quantidade=1, obrigatoria=True)
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)

        # Simula um orçamento pendente criado antes dos campos de hierarquia,
        # quando a peça padrão vinculada ao serviço ficava sem parent_id.
        WorkOrderApprovalBudgetItem.objects.filter(
            orcamento=budget,
            tipo=WorkOrderApprovalItemType.PART,
        ).update(parent=None, peca_obrigatoria=True)
        rows = list(budget.customer_visible_items_ordered)
        service_row = next(row for row in rows if row.tipo == WorkOrderApprovalItemType.SERVICE)

        self.assertFalse(budget.allows_partial_approval)
        self.assertIn('apenas um serviço com peças obrigatórias', budget.partial_approval_block_reason())
        with self.assertRaisesMessage(ValueError, 'apenas um serviço'):
            budget.apply_decision(
                WorkOrderApprovalDecision.APPROVE_PARTIAL,
                approved_item_ids=[service_row.pk],
                responsible_name='Cliente Teste',
                document='12345678901',
            )

        budget.refresh_from_db()
        self.assertEqual(budget.status, WorkOrderApprovalStatus.PENDING)
        self.assertFalse(budget.itens.exclude(aprovado__isnull=True).exists())

    def test_public_approval_indivisible_budget_does_not_render_partial_checkboxes(self):
        ServiceDefaultPart.objects.create(service=self.service, item=self.item, quantidade=1, obrigatoria=True)
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)

        response = self.client.get(reverse('work_order_public_approval', args=[budget.token]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="approve_partial"')
        self.assertNotContains(response, 'name="itens_aprovados"')
        self.assertContains(response, 'Aprove integralmente ou recuse tudo')

    def test_partial_approval_can_reject_optional_service_part_only(self):
        optional_item = InventoryItem.objects.create(
            nome='Aditivo opcional',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('10.00'),
            preco_venda=Decimal('30.00'),
        )
        ServiceDefaultPart.objects.create(service=self.service, item=self.item, quantidade=1, obrigatoria=True)
        ServiceDefaultPart.objects.create(service=self.service, item=optional_item, quantidade=1, obrigatoria=False)
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)
        rows = list(budget.customer_visible_items_ordered)
        service_row = rows[0]
        mandatory_row = next(row for row in rows if row.nome == 'Filtro de ar')
        optional_row = next(row for row in rows if row.nome == 'Aditivo opcional')

        budget.apply_decision(
            WorkOrderApprovalDecision.APPROVE_PARTIAL,
            approved_item_ids=[service_row.pk, mandatory_row.pk],
            responsible_name='Cliente Teste',
            document='12345678901',
        )
        budget.refresh_from_db()
        service_row.refresh_from_db()
        mandatory_row.refresh_from_db()
        optional_row.refresh_from_db()

        self.assertTrue(service_row.aprovado)
        self.assertTrue(mandatory_row.aprovado)
        self.assertFalse(optional_row.aprovado)
        self.assertEqual(order.valor_total, Decimal('150.00'))

    def test_single_service_partial_approval_forces_mandatory_part_when_omitted(self):
        optional_item = InventoryItem.objects.create(
            nome='Aditivo opcional',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('10.00'),
            preco_venda=Decimal('30.00'),
        )
        ServiceDefaultPart.objects.create(service=self.service, item=self.item, quantidade=1, obrigatoria=True)
        ServiceDefaultPart.objects.create(service=self.service, item=optional_item, quantidade=1, obrigatoria=False)
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)
        rows = list(budget.customer_visible_items_ordered)
        service_row = rows[0]
        mandatory_row = next(row for row in rows if row.nome == 'Filtro de ar')
        optional_row = next(row for row in rows if row.nome == 'Aditivo opcional')

        self.assertTrue(budget.allows_partial_approval)
        self.assertEqual(budget.partial_approval_locked_item_ids(), {service_row.pk, mandatory_row.pk})

        budget.apply_decision(
            WorkOrderApprovalDecision.APPROVE_PARTIAL,
            approved_item_ids=[service_row.pk],
            responsible_name='Cliente Teste',
            document='12345678901',
        )
        budget.refresh_from_db()
        service_row.refresh_from_db()
        mandatory_row.refresh_from_db()
        optional_row.refresh_from_db()

        self.assertEqual(budget.status, WorkOrderApprovalStatus.PARTIALLY_APPROVED)
        self.assertTrue(service_row.aprovado)
        self.assertTrue(mandatory_row.aprovado)
        self.assertFalse(optional_row.aprovado)
        self.assertEqual(order.valor_total, Decimal('150.00'))

    def test_public_approval_locks_single_service_mandatory_part_when_optional_exists(self):
        optional_item = InventoryItem.objects.create(
            nome='Aditivo opcional',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('10.00'),
            preco_venda=Decimal('30.00'),
        )
        ServiceDefaultPart.objects.create(service=self.service, item=self.item, quantidade=1, obrigatoria=True)
        ServiceDefaultPart.objects.create(service=self.service, item=optional_item, quantidade=1, obrigatoria=False)
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)

        response = self.client.get(reverse('work_order_public_approval', args=[budget.token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="approve_partial"')
        self.assertContains(response, 'data-approval-locked="true"', count=4)
        self.assertContains(response, 'Peça obrigatória vinculada ao serviço único')

    def test_partial_approval_rejects_service_when_mandatory_part_is_rejected(self):
        optional_item = InventoryItem.objects.create(
            nome='Aditivo opcional',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('10.00'),
            preco_venda=Decimal('30.00'),
        )
        independent_item = InventoryItem.objects.create(
            nome='Lâmpada avulsa',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('8.00'),
            preco_venda=Decimal('20.00'),
        )
        ServiceDefaultPart.objects.create(service=self.service, item=self.item, quantidade=1, obrigatoria=True)
        ServiceDefaultPart.objects.create(service=self.service, item=optional_item, quantidade=1, obrigatoria=False)
        order = self._work_order(status=WorkOrderStatus.AGUARDANDO_APROVACAO)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        WorkOrderPartItem.objects.create(ordem_servico=order, item=independent_item, quantidade=1)
        budget = WorkOrderApprovalBudget.create_from_work_order(order)
        rows = list(budget.customer_visible_items_ordered)
        service_row = rows[0]
        optional_row = next(row for row in rows if row.nome == 'Aditivo opcional')
        mandatory_row = next(row for row in rows if row.nome == 'Filtro de ar')
        independent_row = next(row for row in rows if row.nome == 'Lâmpada avulsa')

        budget.apply_decision(
            WorkOrderApprovalDecision.APPROVE_PARTIAL,
            approved_item_ids=[service_row.pk, optional_row.pk, independent_row.pk],
            responsible_name='Cliente Teste',
            document='12345678901',
        )
        budget.refresh_from_db()
        service_row.refresh_from_db()
        optional_row.refresh_from_db()
        mandatory_row.refresh_from_db()
        independent_row.refresh_from_db()

        self.assertFalse(service_row.aprovado)
        self.assertFalse(optional_row.aprovado)
        self.assertFalse(mandatory_row.aprovado)
        self.assertTrue(independent_row.aprovado)
        self.assertEqual(order.valor_total, Decimal('20.00'))

    def test_duracao_total_minutos(self):
        order = self._work_order()
        # Service default duração is 60 min.
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=2)
        self.assertEqual(order.duracao_total_minutos, 120)


class MechanicKanbanTests(WorkOrderFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.technician = User.objects.create_user(
            email='tecnico@example.com',
            password='senha-teste',
            nome_razao_social='Técnico Teste',
            role=EmployeeRole.TECNICO,
        )
        self.other_technician = User.objects.create_user(
            email='outro.tecnico@example.com',
            password='senha-teste',
            nome_razao_social='Outro Técnico',
            role=EmployeeRole.TECNICO,
        )

    def _items_formset_payload(self, service=None, combo=None, part=None):
        service = service or self.service
        part = part or self.item
        if combo is None:
            combo = ServiceCombo.objects.create(nome='Combo técnico teste')
            ServiceComboItem.objects.create(combo=combo, service=self.service)

        return {
            'services-TOTAL_FORMS': '1',
            'services-INITIAL_FORMS': '0',
            'services-MIN_NUM_FORMS': '0',
            'services-MAX_NUM_FORMS': '1000',
            'services-0-service': str(service.pk),
            'services-0-quantidade': '1',
            'combos-TOTAL_FORMS': '1',
            'combos-INITIAL_FORMS': '0',
            'combos-MIN_NUM_FORMS': '0',
            'combos-MAX_NUM_FORMS': '1000',
            'combos-0-combo': str(combo.pk),
            'combos-0-quantidade': '1',
            'parts-TOTAL_FORMS': '1',
            'parts-INITIAL_FORMS': '0',
            'parts-MIN_NUM_FORMS': '0',
            'parts-MAX_NUM_FORMS': '1000',
            'parts-0-item': str(part.pk),
            'parts-0-quantidade': '2',
        }

    def test_kanban_lists_unassigned_and_own_orders_only(self):
        own_order = self._work_order(tecnico_responsavel=self.technician)
        free_order = self._work_order(status=WorkOrderStatus.APROVADA)
        other_order = self._work_order(tecnico_responsavel=self.other_technician)

        self.client.force_login(self.technician)
        response = self.client.get(reverse('mechanic_kanban'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_order.codigo)
        self.assertContains(response, free_order.codigo)
        self.assertNotContains(response, other_order.codigo)

    def test_move_claims_unassigned_order_and_transitions_status(self):
        order = self._work_order()

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_kanban_move', kwargs={'pk': order.pk}),
            {'status': WorkOrderStatus.DIAGNOSTICO},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        order.refresh_from_db()
        self.assertEqual(order.status, WorkOrderStatus.DIAGNOSTICO)
        self.assertEqual(order.tecnico_responsavel, self.technician)

    def test_move_does_not_allow_order_from_another_technician(self):
        order = self._work_order(tecnico_responsavel=self.other_technician)

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_kanban_move', kwargs={'pk': order.pk}),
            {'status': WorkOrderStatus.DIAGNOSTICO},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 404)

    def test_kanban_is_button_based_and_shows_diagnosis_action(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO, tecnico_responsavel=self.technician)

        self.client.force_login(self.technician)
        response = self.client.get(reverse('mechanic_kanban'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.codigo)
        self.assertContains(response, 'Adicionar diagnóstico')
        self.assertContains(response, '+ Serviço')
        self.assertContains(response, '+ Combo')
        self.assertContains(response, '+ Peça')
        self.assertContains(response, 'data-kanban-add-item')
        self.assertContains(response, reverse('mechanic_kanban_add_item', kwargs={'pk': order.pk}))
        self.assertContains(response, 'mechanic_kanban_service_picker_modal')
        self.assertContains(response, 'static/js/reusable-select-modal.js')
        self.assertNotContains(response, reverse('mechanic_work_order_items', kwargs={'pk': order.pk}) + '?adicionar=servico')
        self.assertNotContains(response, 'draggable=')

    def test_diagnosis_view_saves_diagnosis_and_claims_free_order(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO)

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_work_order_diagnosis', kwargs={'pk': order.pk}),
            {'diagnostico': 'Falha no sensor MAP após teste com scanner.'},
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.diagnostico, 'Falha no sensor MAP após teste com scanner.')
        self.assertEqual(order.tecnico_responsavel, self.technician)

    def test_diagnosis_view_can_save_and_send_to_budget(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO, tecnico_responsavel=self.technician)

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_work_order_diagnosis', kwargs={'pk': order.pk}),
            {
                'diagnostico': 'Necessário substituir vela e cabo de ignição.',
                'next_action': 'orcamento',
            },
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.diagnostico, 'Necessário substituir vela e cabo de ignição.')
        self.assertEqual(order.status, WorkOrderStatus.ORCAMENTO)

    def test_diagnosis_view_shows_ai_helper_with_order_context(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO, tecnico_responsavel=self.technician)
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)

        self.client.force_login(self.technician)
        response = self.client.get(reverse('mechanic_work_order_diagnosis', kwargs={'pk': order.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'IA preencher/detalhar')
        self.assertContains(response, 'data-ai-action="improve_diagnosis"')
        self.assertContains(response, "static/js/ai-assistant.js")
        self.assertContains(response, 'Motor com ruído')
        self.assertContains(response, 'Diagnóstico (qtd. 1)')


    def test_technical_items_view_adds_service_combo_and_part(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO, tecnico_responsavel=self.technician)

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_work_order_items', kwargs={'pk': order.pk}),
            self._items_formset_payload(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(WorkOrderServiceItem.objects.filter(ordem_servico=order).count(), 1)
        self.assertEqual(WorkOrderComboItem.objects.filter(ordem_servico=order).count(), 1)
        self.assertEqual(WorkOrderPartItem.objects.filter(ordem_servico=order).count(), 1)
        self.assertEqual(WorkOrderPartItem.objects.get(ordem_servico=order).quantidade, 2)

    def test_technical_items_view_claims_free_order_when_saving(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO)

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_work_order_items', kwargs={'pk': order.pk}),
            self._items_formset_payload(),
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.tecnico_responsavel, self.technician)

    def test_technical_items_view_can_auto_open_part_picker(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO, tecnico_responsavel=self.technician)

        self.client.force_login(self.technician)
        response = self.client.get(
            reverse('mechanic_work_order_items', kwargs={'pk': order.pk}),
            {'adicionar': 'peca'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-work-order-auto-open="peca"')
        self.assertContains(response, 'Adicionar peça')

    def test_kanban_add_item_endpoint_adds_service_without_leaving_board(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO, tecnico_responsavel=self.technician)

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_kanban_add_item', kwargs={'pk': order.pk}),
            {'item_type': 'servico', 'item_id': str(self.service.pk), 'quantidade': '2'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('card_html', payload)
        line = WorkOrderServiceItem.objects.get(ordem_servico=order, service=self.service)
        self.assertEqual(line.quantidade, 2)

    def test_kanban_add_item_endpoint_adds_combo_and_part(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO, tecnico_responsavel=self.technician)
        combo = ServiceCombo.objects.create(nome='Combo direto no Kanban')
        ServiceComboItem.objects.create(combo=combo, service=self.service)

        self.client.force_login(self.technician)
        combo_response = self.client.post(
            reverse('mechanic_kanban_add_item', kwargs={'pk': order.pk}),
            {'item_type': 'combo', 'item_id': str(combo.pk), 'quantidade': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        part_response = self.client.post(
            reverse('mechanic_kanban_add_item', kwargs={'pk': order.pk}),
            {'item_type': 'peca', 'item_id': str(self.item.pk), 'quantidade': '3'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(combo_response.status_code, 200)
        self.assertEqual(part_response.status_code, 200)
        self.assertTrue(combo_response.json()['ok'])
        self.assertTrue(part_response.json()['ok'])
        self.assertEqual(WorkOrderComboItem.objects.filter(ordem_servico=order, combo=combo).count(), 1)
        self.assertEqual(WorkOrderPartItem.objects.get(ordem_servico=order, item=self.item).quantidade, 3)

    def test_kanban_add_item_endpoint_increments_existing_item_quantity(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO, tecnico_responsavel=self.technician)
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.item, quantidade=1)

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_kanban_add_item', kwargs={'pk': order.pk}),
            {'item_type': 'peca', 'item_id': str(self.item.pk), 'quantidade': '2'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        line = WorkOrderPartItem.objects.get(ordem_servico=order, item=self.item)
        self.assertEqual(line.quantidade, 3)

    def test_kanban_add_item_endpoint_claims_free_order(self):
        order = self._work_order(status=WorkOrderStatus.DIAGNOSTICO)

        self.client.force_login(self.technician)
        response = self.client.post(
            reverse('mechanic_kanban_add_item', kwargs={'pk': order.pk}),
            {'item_type': 'servico', 'item_id': str(self.service.pk), 'quantidade': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        order.refresh_from_db()
        self.assertEqual(order.tecnico_responsavel, self.technician)


class MechanicKanbanAdminAccessTests(WorkOrderFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = User.objects.create_user(
            email='admin.operacional@example.com',
            password='senha-teste',
            nome_razao_social='Admin Operacional',
            role=EmployeeRole.ADM,
        )
        self.technician = User.objects.create_user(
            email='tecnico.admin.access@example.com',
            password='senha-teste',
            nome_razao_social='Técnico Responsável',
            role=EmployeeRole.TECNICO,
        )

    def test_administrative_user_can_access_mechanic_kanban_and_see_all_orders(self):
        assigned_order = self._work_order(tecnico_responsavel=self.technician)
        free_order = self._work_order(status=WorkOrderStatus.APROVADA)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('mechanic_kanban'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, assigned_order.codigo)
        self.assertContains(response, free_order.codigo)

    def test_administrative_user_can_move_order_assigned_to_technician(self):
        order = self._work_order(tecnico_responsavel=self.technician)

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('mechanic_kanban_move', kwargs={'pk': order.pk}),
            {'status': WorkOrderStatus.DIAGNOSTICO},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        order.refresh_from_db()
        self.assertEqual(order.status, WorkOrderStatus.DIAGNOSTICO)
        self.assertEqual(order.tecnico_responsavel, self.technician)


class CustomerVehicleHistoryAccessTests(WorkOrderFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vehicle = Vehicle.objects.create(
            cliente=self.customer,
            placa='ABC1D23',
            marca='Volkswagen',
            modelo='Gol',
            km=12345,
        )

    def test_plate_request_sends_six_digit_code_to_customer_email(self):
        response = self.client.post(reverse('customer_vehicle_access_request'), {'placa': 'abc1d23'})

        self.assertEqual(response.status_code, 302)
        access = CustomerVehicleAccessToken.objects.get(veiculo=self.vehicle)
        self.assertIn(str(access.token), response['Location'])
        self.assertEqual(access.email, self.customer.email)
        self.assertGreater(access.expira_em, timezone.now())
        self.assertLessEqual(access.expira_em, timezone.now() + timedelta(hours=5, minutes=1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Código de acesso ao histórico do veículo', mail.outbox[0].subject)
        self.assertRegex(mail.outbox[0].body, r'\b\d{6}\b')

    def test_unknown_plate_does_not_send_email_or_create_token(self):
        response = self.client.post(reverse('customer_vehicle_access_request'), {'placa': 'ZZZ9Z99'})

        self.assertRedirects(response, reverse('customer_vehicle_access_request'))
        self.assertEqual(CustomerVehicleAccessToken.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_valid_code_unlocks_history_and_hides_internal_supplies(self):
        order = self._work_order(veiculo=self.vehicle, status=WorkOrderStatus.EM_EXECUCAO, diagnostico='Troca necessária')
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=1)
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.item, quantidade=1)
        WorkOrderPartItem.objects.create(ordem_servico=order, item=self.insumo, quantidade=1)
        access = CustomerVehicleAccessToken.create_for_vehicle(self.vehicle, code='123456')

        verify_response = self.client.post(
            reverse('customer_vehicle_access_verify', kwargs={'token': access.token}),
            {'codigo': '123456'},
        )
        self.assertRedirects(verify_response, reverse('customer_vehicle_history', kwargs={'token': access.token}))

        history_response = self.client.get(reverse('customer_vehicle_history', kwargs={'token': access.token}))
        self.assertEqual(history_response.status_code, 200)
        self.assertContains(history_response, order.codigo)
        self.assertContains(history_response, 'customer-history-timeline')
        self.assertNotContains(history_response, 'lg:timeline-horizontal')
        self.assertContains(history_response, self.service.nome)
        self.assertContains(history_response, self.item.nome)
        self.assertNotContains(history_response, self.insumo.nome)

    def test_history_requires_verified_session(self):
        access = CustomerVehicleAccessToken.create_for_vehicle(self.vehicle, code='123456')

        response = self.client.get(reverse('customer_vehicle_history', kwargs={'token': access.token}))

        self.assertRedirects(response, reverse('customer_vehicle_access_verify', kwargs={'token': access.token}))

    def test_expired_code_is_rejected(self):
        access = CustomerVehicleAccessToken.create_for_vehicle(self.vehicle, code='123456')
        CustomerVehicleAccessToken.objects.filter(pk=access.pk).update(expira_em=timezone.now() - timedelta(minutes=1))

        response = self.client.post(
            reverse('customer_vehicle_access_verify', kwargs={'token': access.token}),
            {'codigo': '123456'},
        )

        self.assertRedirects(response, reverse('customer_vehicle_access_request'))
        access.refresh_from_db()
        self.assertIsNone(access.verificado_em)
