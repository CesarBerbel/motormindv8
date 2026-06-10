from django import forms
from django.forms import formset_factory, inlineformset_factory
from django.db.models.functions import Lower

from core.forms import BASE_INPUT_CLASS, BASE_SELECT_CLASS, DaisyFormMixin
from core.models import Supplier
from core.money import MoneyFormField

from .models import Brand, InventoryItem, InventoryItemType, MIN_QUANTITY, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, StockCategory, StockMovement, StockMovementType, UnitOfMeasure, ZERO_QUANTITY

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
    preco_venda = MoneyFormField(label='Preço de venda')

    class Meta:
        model = InventoryItem
        fields = [
            'sku',
            'tipo',
            'nome',
            'descricao',
            'categoria',
            'marca',
            'estoque_minimo',
            'unidade',
            'preco_custo',
            'preco_venda',
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'estoque_minimo': forms.NumberInput(attrs={'step': '1', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['sku'].required = False
        self.fields['sku'].help_text = 'Opcional. Se ficar vazio, o sistema gera um SKU automaticamente.'
        self.fields['sku'].widget.attrs.update({
            'placeholder': 'Ex.: FILTRO-001',
            'autocomplete': 'off',
        })
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

    def clean_sku(self):
        value = (self.cleaned_data.get('sku') or '').strip()
        return value or None

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


class InventoryXmlUploadForm(DaisyFormMixin, forms.Form):
    arquivo = forms.FileField(
        label='Arquivo XML ou ZIP',
        help_text='Envie uma NF-e em XML ou um ZIP contendo um ou mais XMLs de NF-e.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['arquivo'].widget.attrs.update({
            'accept': '.xml,.zip,application/xml,text/xml,application/zip',
            'class': 'file-input file-input-bordered w-full',
        })

    def clean_arquivo(self):
        arquivo = self.cleaned_data['arquivo']
        nome = (arquivo.name or '').lower()
        if not (nome.endswith('.xml') or nome.endswith('.zip')):
            raise forms.ValidationError('Envie um arquivo .xml ou .zip.')
        return arquivo


class InventoryXmlImportOptionsForm(DaisyFormMixin, forms.Form):
    fornecedor = forms.ModelChoiceField(
        label='Fornecedor para entrada de estoque',
        queryset=Supplier.objects.none(),
        required=False,
        help_text='Opcional. Necessário somente se quiser registrar a entrada de estoque automaticamente.',
    )
    registrar_entrada = forms.BooleanField(
        label='Registrar entrada de estoque com as quantidades do XML',
        required=False,
        initial=False,
    )
    atualizar_existentes = forms.BooleanField(
        label='Atualizar itens já existentes pelo código da peça/SKU',
        required=False,
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        fornecedor_initial = kwargs.pop('fornecedor_initial', None)
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['fornecedor'].queryset = Supplier.objects.order_by(Lower('nome_razao_social'), 'pk')
        if fornecedor_initial:
            self.fields['fornecedor'].initial = fornecedor_initial
        self.fields['registrar_entrada'].widget.attrs.setdefault('class', 'checkbox checkbox-primary')
        self.fields['atualizar_existentes'].widget.attrs.setdefault('class', 'checkbox checkbox-primary')

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('registrar_entrada') and not cleaned_data.get('fornecedor'):
            self.add_error('fornecedor', 'Selecione o fornecedor para registrar entrada de estoque.')
        return cleaned_data


class InventoryXmlImportItemForm(DaisyFormMixin, forms.Form):
    line_id = forms.CharField(widget=forms.HiddenInput)
    xml_codigo = forms.CharField(required=False, widget=forms.HiddenInput)
    xml_ean = forms.CharField(required=False, widget=forms.HiddenInput)
    xml_ncm = forms.CharField(required=False, widget=forms.HiddenInput)
    xml_cfop = forms.CharField(required=False, widget=forms.HiddenInput)
    xml_unidade = forms.CharField(required=False, widget=forms.HiddenInput)
    quantidade_original = forms.CharField(required=False, widget=forms.HiddenInput)
    importar = forms.BooleanField(label='Importar?', required=False, initial=True)
    sku = forms.CharField(
        label='Código da peça',
        max_length=60,
        required=False,
        help_text='Vem do cProd do XML quando disponível. Pode ser editado antes de importar.',
    )
    nome = forms.CharField(label='Nome', max_length=180)
    tipo = forms.ChoiceField(label='Tipo', choices=InventoryItemType.choices)
    categoria = forms.ModelChoiceField(label='Categoria', queryset=StockCategory.objects.none(), required=False)
    marca = forms.ModelChoiceField(label='Marca', queryset=Brand.objects.none(), required=False)
    unidade = forms.ModelChoiceField(label='Unidade', queryset=UnitOfMeasure.objects.none())
    estoque_minimo = forms.IntegerField(label='Estoque mínimo', min_value=0, initial=0)
    quantidade = forms.IntegerField(label='Quantidade XML', min_value=0, initial=0)
    preco_custo = MoneyFormField(label='Preço de custo')
    preco_venda = MoneyFormField(label='Preço de venda')
    descricao = forms.CharField(label='Descrição', required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['categoria'].queryset = StockCategory.objects.order_by(Lower('nome'), 'pk')
        self.fields['marca'].queryset = Brand.objects.order_by(Lower('nome'), 'pk')
        self.fields['unidade'].queryset = UnitOfMeasure.objects.filter(ativo=True).order_by(Lower('nome'), 'pk')
        self.fields['importar'].widget.attrs.setdefault('class', 'checkbox checkbox-primary')
        self.fields['sku'].widget.attrs.update({
            'placeholder': 'Código do XML ou código interno',
            'autocomplete': 'off',
        })
        for field_name in ['estoque_minimo', 'quantidade']:
            self.fields[field_name].widget.attrs.update({
                'class': QUANTITY_INPUT_CLASS,
                'inputmode': 'numeric',
            })

    def clean_sku(self):
        value = (self.cleaned_data.get('sku') or '').strip()
        return value or None

    def clean_estoque_minimo(self):
        value = self.cleaned_data.get('estoque_minimo')
        return value if value is not None else ZERO_QUANTITY

    def clean_quantidade(self):
        value = self.cleaned_data.get('quantidade')
        return value if value is not None else ZERO_QUANTITY


InventoryXmlImportItemFormSet = formset_factory(
    InventoryXmlImportItemForm,
    extra=0,
    can_delete=False,
)
