from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations
import core.money


def copy_cost_to_sale_price(apps, schema_editor):
    InventoryItem = apps.get_model('stock', 'InventoryItem')
    for item in InventoryItem.objects.all().only('pk', 'preco_custo', 'preco_venda'):
        if item.preco_venda in (None, Decimal('0.00')):
            item.preco_venda = item.preco_custo or Decimal('0.00')
            item.save(update_fields=['preco_venda'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0004_purchase_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitem',
            name='preco_venda',
            field=core.money.MoneyField(decimal_places=2, default=Decimal('0.00'), max_digits=12, validators=[MinValueValidator(Decimal('0'))], verbose_name='Preço de venda'),
        ),
        migrations.RunPython(copy_cost_to_sale_price, migrations.RunPython.noop),
    ]
