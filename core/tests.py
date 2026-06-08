from decimal import Decimal

from django import forms
from django.test import SimpleTestCase

from core.money import MoneyField, format_money_br, normalize_money


class NormalizeMoneyTests(SimpleTestCase):
    def test_brazilian_format_with_thousands_separator(self):
        self.assertEqual(normalize_money('1.234,56'), Decimal('1234.56'))

    def test_plain_decimal_format(self):
        self.assertEqual(normalize_money('1234.56'), Decimal('1234.56'))

    def test_strips_currency_symbol_and_spaces(self):
        self.assertEqual(normalize_money('R$ 1.234,56'), Decimal('1234.56'))

    def test_decimal_input_is_quantized_to_two_places(self):
        self.assertEqual(normalize_money(Decimal('10.005')), Decimal('10.01'))

    def test_empty_and_none_return_none(self):
        self.assertIsNone(normalize_money(''))
        self.assertIsNone(normalize_money(None))

    def test_invalid_value_raises_validation_error(self):
        with self.assertRaises(forms.ValidationError):
            normalize_money('abc')


class FormatMoneyBrTests(SimpleTestCase):
    def test_formats_thousands_and_decimals(self):
        self.assertEqual(format_money_br(Decimal('1234.56')), 'R$ 1.234,56')

    def test_none_returns_zero(self):
        self.assertEqual(format_money_br(None), 'R$ 0,00')

    def test_zero(self):
        self.assertEqual(format_money_br(Decimal('0')), 'R$ 0,00')


class MoneyFieldTests(SimpleTestCase):
    def setUp(self):
        self.field = MoneyField()

    def test_to_python_normalizes(self):
        self.assertEqual(self.field.to_python('1.234,56'), Decimal('1234.56'))

    def test_to_python_empty_returns_none(self):
        self.assertIsNone(self.field.to_python(''))

    def test_get_prep_value_normalizes(self):
        self.assertEqual(self.field.get_prep_value('10,50'), Decimal('10.50'))
