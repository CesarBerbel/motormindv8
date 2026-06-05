from decimal import Decimal

MONEY_ZERO = Decimal('0.00')


def money(value):
    if value is None:
        return MONEY_ZERO
    return Decimal(value).quantize(Decimal('0.01'))


def inventory_sale_price(item):
    """Return the price charged to the customer for a stock item.

    New records should have `preco_venda` filled explicitly. For backward
    compatibility with older databases, zero/empty sale prices fall back to
    cost so existing OS totals do not collapse to zero after migration.
    """
    sale_price = getattr(item, 'preco_venda', None)
    if sale_price is not None and sale_price > MONEY_ZERO:
        return money(sale_price)
    return money(getattr(item, 'preco_custo', MONEY_ZERO))


def inventory_margin_value(item):
    return (inventory_sale_price(item) - money(getattr(item, 'preco_custo', MONEY_ZERO))).quantize(Decimal('0.01'))


def inventory_margin_percent(item):
    sale_price = inventory_sale_price(item)
    if sale_price <= MONEY_ZERO:
        return MONEY_ZERO
    return (inventory_margin_value(item) * Decimal('100') / sale_price).quantize(Decimal('0.01'))
