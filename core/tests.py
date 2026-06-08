import json
from decimal import Decimal
from unittest import mock

from django import forms
from django.core.cache import cache
from django.test import SimpleTestCase

from core.money import MoneyField, format_money_br, normalize_money
from core.views import FipeProxyBaseView


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


class FipeCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _fake_response(self, payload):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(payload).encode('utf-8')
        resp.headers.get_content_charset.return_value = 'utf-8'
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    def test_second_call_is_served_from_cache(self):
        view = FipeProxyBaseView()
        payload = [{'code': '1', 'name': 'Fiat'}]
        with mock.patch('core.views.urlopen', return_value=self._fake_response(payload)) as urlopen_mock:
            first = view.fetch_json('/cars/brands')
            second = view.fetch_json('/cars/brands')

        self.assertEqual(first, payload)
        self.assertEqual(second, payload)
        # A segunda chamada vem do cache: urlopen so e invocado uma vez.
        self.assertEqual(urlopen_mock.call_count, 1)

    def test_different_paths_are_cached_separately(self):
        view = FipeProxyBaseView()
        with mock.patch('core.views.urlopen', side_effect=[
            self._fake_response([{'code': '1', 'name': 'A'}]),
            self._fake_response([{'code': '2', 'name': 'B'}]),
        ]) as urlopen_mock:
            view.fetch_json('/cars/brands')
            view.fetch_json('/trucks/brands')

        self.assertEqual(urlopen_mock.call_count, 2)
