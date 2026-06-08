from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from stock.models import (
    InventoryItem,
    StockCategory,
    StockMovement,
    StockMovementType,
    UnitOfMeasure,
)


class StockFixtureMixin:
    def setUp(self):
        super().setUp()
        self.categoria = StockCategory.objects.create(nome='Filtros Teste')
        self.unidade = UnitOfMeasure.objects.create(nome='Unidade Teste', sigla='unt')
        self.item = InventoryItem.objects.create(
            nome='Filtro de oleo',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('5.00'),
            preco_venda=Decimal('12.00'),
        )

    def _move(self, tipo, quantidade, **kwargs):
        movement = StockMovement(item=self.item, tipo=tipo, quantidade=quantidade, **kwargs)
        movement.save()
        return movement


class InventoryItemTests(StockFixtureMixin, TestCase):
    def test_sku_is_generated_on_creation(self):
        self.assertEqual(self.item.sku, f'PCA-{self.item.pk:06d}')

    def test_estoque_atual_starts_at_zero(self):
        self.assertEqual(self.item.estoque_atual, 0)

    def test_estoque_atual_reflects_movements(self):
        self._move(StockMovementType.AJUSTE_POSITIVO, 10)
        self._move(StockMovementType.SAIDA, 3)
        self.assertEqual(self.item.estoque_atual, 7)

    def test_abaixo_estoque_minimo(self):
        self.item.estoque_minimo = 20
        self.item.save(update_fields=['estoque_minimo'])
        self._move(StockMovementType.AJUSTE_POSITIVO, 10)
        self.assertTrue(self.item.abaixo_estoque_minimo)


class StockMovementTests(StockFixtureMixin, TestCase):
    def test_positive_adjustment_sets_signed_and_balance(self):
        movement = self._move(StockMovementType.AJUSTE_POSITIVO, 10)
        self.assertEqual(movement.quantidade_assinada, 10)
        self.assertEqual(movement.saldo_apos_movimentacao, 10)

    def test_outflow_is_signed_negative(self):
        self._move(StockMovementType.AJUSTE_POSITIVO, 10)
        movement = self._move(StockMovementType.SAIDA, 4)
        self.assertEqual(movement.quantidade_assinada, -4)
        self.assertEqual(movement.saldo_apos_movimentacao, 6)

    def test_valor_total_uses_unit_cost(self):
        movement = self._move(
            StockMovementType.AJUSTE_POSITIVO, 10, custo_unitario=Decimal('5.00')
        )
        self.assertEqual(movement.valor_total, Decimal('50.00'))

    def test_unit_cost_defaults_to_item_cost(self):
        movement = self._move(StockMovementType.AJUSTE_POSITIVO, 2)
        self.assertEqual(movement.custo_unitario, Decimal('5.00'))
        self.assertEqual(movement.valor_total, Decimal('10.00'))

    def test_cannot_leave_stock_negative(self):
        self._move(StockMovementType.AJUSTE_POSITIVO, 5)
        with self.assertRaises(ValidationError):
            self._move(StockMovementType.SAIDA, 100)

    def test_saved_movement_cannot_be_edited(self):
        movement = self._move(StockMovementType.AJUSTE_POSITIVO, 5)
        movement.quantidade = 99
        with self.assertRaises(ValidationError):
            movement.save()

    def test_entrada_requires_fornecedor(self):
        with self.assertRaises(ValidationError):
            self._move(StockMovementType.ENTRADA, 5)
