from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from core.models import Customer, PessoaTipo
from operations.models import (
    Service,
    WorkOrder,
    WorkOrderPartItem,
    WorkOrderServiceItem,
    WorkOrderStatus,
)
from operations.services.work_order_pricing import (
    inventory_margin_percent,
    inventory_margin_value,
    inventory_sale_price,
)
from stock.models import InventoryItem, StockCategory, UnitOfMeasure


class _FakeItem:
    def __init__(self, preco_venda, preco_custo):
        self.preco_venda = preco_venda
        self.preco_custo = preco_custo


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

    def test_duracao_total_minutos(self):
        order = self._work_order()
        # Service default duração is 60 min.
        WorkOrderServiceItem.objects.create(ordem_servico=order, service=self.service, quantidade=2)
        self.assertEqual(order.duracao_total_minutos, 120)
