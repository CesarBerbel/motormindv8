from django import forms
from django.forms import inlineformset_factory
from django.db.models.functions import Lower

from core.forms import BASE_INPUT_CLASS, BASE_SELECT_CLASS, DaisyFormMixin
from core.models import Supplier
from core.money import MoneyFormField

from .models import Brand, InventoryItem, MIN_QUANTITY, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, StockCategory, StockMovement, StockMovementType, UnitOfMeasure, ZERO_QUANTITY

QUANTITY_INPUT_CLASS = 'input input-bordered w-full'


class StockCategoryForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = StockCategory
        fields = ['nome', 'descricao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()


class BrandForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['nome']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()


class InventoryItemForm(DaisyFormMixin, forms.ModelForm):
    preco_custo = MoneyFormField(label='Preço de custo')

    class Meta:
        model = InventoryItem
        fields = [
            'tipo',
            'nome',
            'descricao',
            'categoria',
            'marca',
            'estoque_minimo',
            'unidade',
            'preco_custo',
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'estoque_minimo': forms.NumberInput(attrs={'step': '1', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['categoria'].queryset = StockCategory.objects.order_by(Lower('nome'), 'pk')
        self.fields['marca'].queryset = Brand.objects.order_by(Lower('nome'), 'pk')
        self.fields['unidade'].queryset = UnitOfMeasure.objects.filter(ativo=True).order_by(Lower('nome'), 'pk')
        self.fields['marca'].required = False
        self.fields['descricao'].required = False
        self.fields['estoque_minimo'].widget.attrs.update({
            'class': QUANTITY_INPUT_CLASS,
            'placeholder': '0',
            'inputmode': 'numeric',
        })

    def clean_estoque_minimo(self):
        value = self.cleaned_data.get('estoque_minimo')
        if value is None:
            return ZERO_QUANTITY
        if value < ZERO_QUANTITY:
            raise forms.ValidationError('Estoque mínimo não pode ser negativo.')
        return value


class StockMovementForm(DaisyFormMixin, forms.ModelForm):
    custo_unitario = MoneyFormField(label='Custo unitário', required=False)

    class Meta:
        model = StockMovement
        fields = ['item', 'tipo', 'fornecedor', 'quantidade', 'custo_unitario', 'observacao']
        widgets = {
            'quantidade': forms.NumberInput(attrs={'step': '1', 'min': '1'}),
            'observacao': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['item'].queryset = InventoryItem.objects.select_related('categoria', 'marca', 'unidade').order_by(Lower('nome'), 'pk')
        self.fields['fornecedor'].queryset = Supplier.objects.order_by(Lower('nome_razao_social'), 'pk')
        self.fields['fornecedor'].required = False
        self.fields['fornecedor'].help_text = 'Obrigatório somente para movimentações de entrada.'
        self.fields['observacao'].required = False
        self.fields['quantidade'].widget.attrs.update({
            'class': QUANTITY_INPUT_CLASS,
            'placeholder': '1',
            'inputmode': 'numeric',
        })

    def clean_quantidade(self):
        value = self.cleaned_data.get('quantidade')
        if value is None or value < MIN_QUANTITY:
            raise forms.ValidationError('Informe uma quantidade inteira maior que zero.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        fornecedor = cleaned_data.get('fornecedor')

        if tipo == StockMovementType.ENTRADA and not fornecedor:
            self.add_error('fornecedor', 'Informe o fornecedor para movimentações de entrada.')

        if tipo and tipo != StockMovementType.ENTRADA:
            cleaned_data['fornecedor'] = None

        return cleaned_data



class PurchaseOrderForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['fornecedor', 'status', 'observacao']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['fornecedor'].queryset = Supplier.objects.order_by(Lower('nome_razao_social'), 'pk')
        self.fields['fornecedor'].required = False
        self.fields['fornecedor'].help_text = 'Pode ficar vazio enquanto o pedido estiver pendente. Obrigatório para receber o pedido.'
        self.fields['status'].choices = [
            (PurchaseOrderStatus.PENDENTE, 'Pendente'),
            (PurchaseOrderStatus.SOLICITADO, 'Solicitado'),
            (PurchaseOrderStatus.CANCELADO, 'Cancelado'),
        ]
        self.fields['observacao'].required = False


class PurchaseOrderItemForm(DaisyFormMixin, forms.ModelForm):
    custo_unitario = MoneyFormField(label='Custo unitário', required=False)

    class Meta:
        model = PurchaseOrderItem
        fields = ['item', 'quantidade', 'custo_unitario', 'observacao']
        widgets = {
            'quantidade': forms.NumberInput(attrs={'step': '1', 'min': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['item'].queryset = InventoryItem.objects.select_related('categoria', 'marca', 'unidade').order_by(Lower('nome'), 'pk')
        self.fields['quantidade'].widget.attrs.update({
            'class': QUANTITY_INPUT_CLASS,
            'placeholder': '1',
            'inputmode': 'numeric',
        })
        self.fields['observacao'].required = False

    def clean_quantidade(self):
        value = self.cleaned_data.get('quantidade')
        if value is None or value < MIN_QUANTITY:
            raise forms.ValidationError('Informe uma quantidade inteira maior que zero.')
        return value


PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=5,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
