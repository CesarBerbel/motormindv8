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


class InventoryItemManualSkuTests(StockFixtureMixin, TestCase):
    def test_manual_sku_is_preserved_on_creation(self):
        item = InventoryItem.objects.create(
            sku='XML-ABC-123',
            nome='Filtro importado XML',
            categoria=self.categoria,
            unidade=self.unidade,
            preco_custo=Decimal('10.00'),
            preco_venda=Decimal('15.00'),
        )

        self.assertEqual(item.sku, 'XML-ABC-123')


class InventoryXmlParserTests(TestCase):
    def test_parse_nfe_products_maps_xml_fields_to_inventory_fields(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from stock.services.xml_inventory_import import parse_inventory_xml_upload

        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
          <NFe>
            <infNFe Id="NFe35123456789012345678901234567890123456789012">
              <ide><nNF>123</nNF></ide>
              <emit>
                <CNPJ>12345678000190</CNPJ>
                <xNome>Fornecedor Teste</xNome>
                <enderEmit><xMun>Sao Paulo</xMun><UF>SP</UF></enderEmit>
              </emit>
              <det nItem="1">
                <prod>
                  <cProd>FILTRO-001</cProd>
                  <cEAN>7891234567890</cEAN>
                  <xProd>Filtro de oleo importado</xProd>
                  <NCM>84212300</NCM>
                  <CFOP>5102</CFOP>
                  <uCom>UN</uCom>
                  <qCom>2.0000</qCom>
                  <vUnCom>25.50</vUnCom>
                  <vProd>51.00</vProd>
                </prod>
              </det>
            </infNFe>
          </NFe>
        </nfeProc>""".encode('utf-8')

        uploaded = SimpleUploadedFile('nfe.xml', xml, content_type='application/xml')
        documents = parse_inventory_xml_upload(uploaded)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].numero, '123')
        self.assertEqual(documents[0].fornecedor.documento, '12345678000190')
        self.assertEqual(len(documents[0].produtos), 1)

        product = documents[0].produtos[0]
        self.assertEqual(product.codigo, 'FILTRO-001')
        self.assertEqual(product.codigo_barras, '7891234567890')
        self.assertEqual(product.nome, 'Filtro de oleo importado')
        self.assertEqual(product.unidade_sigla, 'UN')
        self.assertEqual(product.quantidade, '2')
        self.assertEqual(product.preco_unitario, '25.50')
        self.assertEqual(product.valor_total, '51.00')
        self.assertIn('NCM: 84212300', product.descricao)
