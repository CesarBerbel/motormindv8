from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import forms
from django.core.validators import MinValueValidator
from django.db import models

MONEY_MAX_DIGITS = 12
MONEY_DECIMAL_PLACES = 2
MONEY_QUANTIZER = Decimal('0.01')


def normalize_money(value):
    if value is None or value == '':
        return None

    if isinstance(value, Decimal):
        amount = value
    else:
        text = str(value).strip()
        text = text.replace('R$', '').replace(' ', '')

        if ',' in text:
            text = text.replace('.', '').replace(',', '.')

        try:
            amount = Decimal(text)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Informe um valor monetário válido.')

    return amount.quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def format_money_br(value):
    amount = normalize_money(value)
    if amount is None:
        return 'R$ 0,00'

    formatted = f'{amount:,.2f}'
    formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatted}'


class MoneyField(models.DecimalField):
    description = 'Valor monetário com duas casas decimais'

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', MONEY_MAX_DIGITS)
        kwargs.setdefault('decimal_places', MONEY_DECIMAL_PLACES)
        kwargs.setdefault('validators', [MinValueValidator(Decimal('0'))])
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value is None or value == '':
            return None
        return normalize_money(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return None
        return normalize_money(value)


class MoneyFormField(forms.DecimalField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', MONEY_MAX_DIGITS)
        kwargs.setdefault('decimal_places', MONEY_DECIMAL_PLACES)
        kwargs.setdefault('min_value', Decimal('0'))
        kwargs.setdefault('widget', forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'inputmode': 'decimal',
            'placeholder': '0,00',
            'data-mask': 'money',
        }))
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        return normalize_money(value)
