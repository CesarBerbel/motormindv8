from datetime import date

from django import forms

from .models import (
    Category,
    CategoryAudience,
    Customer,
    PessoaTipo,
    Supplier,
    Vehicle,
    VehicleDirectionType,
    VehicleFipeType,
    VehicleFuelType,
    format_plate,
    only_alnum_upper,
    only_digits,
)

BASE_INPUT_CLASS = 'input input-bordered w-full'
BASE_SELECT_CLASS = 'select select-bordered w-full'
BASE_CHECKBOX_CLASS = 'checkbox checkbox-primary'
BASE_MULTISELECT_CLASS = 'select select-bordered w-full min-h-32'
DATE_INPUT_FORMATS = ['%Y-%m-%d']


def format_cpf(value):
    digits = only_digits(value)[:11]
    if len(digits) <= 3:
        return digits
    if len(digits) <= 6:
        return f'{digits[:3]}.{digits[3:]}'
    if len(digits) <= 9:
        return f'{digits[:3]}.{digits[3:6]}.{digits[6:]}'
    return f'{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}'


def format_cnpj(value):
    digits = only_digits(value)[:14]
    if len(digits) <= 2:
        return digits
    if len(digits) <= 5:
        return f'{digits[:2]}.{digits[2:]}'
    if len(digits) <= 8:
        return f'{digits[:2]}.{digits[2:5]}.{digits[5:]}'
    if len(digits) <= 12:
        return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:]}'
    return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}'


def format_phone(value):
    digits = only_digits(value)[:11]
    if len(digits) <= 2:
        return digits
    if len(digits) <= 6:
        return f'({digits[:2]}) {digits[2:]}'
    if len(digits) <= 10:
        return f'({digits[:2]}) {digits[2:6]}-{digits[6:]}'
    return f'({digits[:2]}) {digits[2:7]}-{digits[7:]}'


def format_cep(value):
    digits = only_digits(value)[:8]
    if len(digits) <= 5:
        return digits
    return f'{digits[:5]}-{digits[5:]}'


def normalize_email(value):
    return (value or '').strip().lower()


class DaisyFormMixin:
    date_fields = {'data_nascimento_fundacao'}

    def apply_daisy_classes(self):
        for name, field in self.fields.items():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', BASE_CHECKBOX_CLASS)
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs.setdefault('class', BASE_CHECKBOX_CLASS)
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs.setdefault('class', BASE_MULTISELECT_CLASS)
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', BASE_SELECT_CLASS)
            else:
                widget.attrs.setdefault('class', BASE_INPUT_CLASS)

            if name in self.date_fields:
                widget.input_type = 'date'
                widget.attrs['type'] = 'date'


class PessoaFormMixin(DaisyFormMixin):
    fields = [
        'tipo_pessoa',
        'nome_razao_social',
        'documento',
        'data_nascimento_fundacao',
        'email',
        'whatsapp',
        'cep',
        'logradouro',
        'numero',
        'complemento',
        'bairro',
        'cidade',
        'uf',
        'aceita_marketing',
        'categorias',
    ]

    duplicate_models = (Customer, Supplier)
    default_tipo_pessoa = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.default_tipo_pessoa and not self.is_bound and not getattr(self.instance, 'pk', None):
            self.initial['tipo_pessoa'] = self.default_tipo_pessoa
            self.fields['tipo_pessoa'].initial = self.default_tipo_pessoa

        today = date.today().strftime('%Y-%m-%d')

        self.apply_daisy_classes()
        self.fields['documento'].required = False
        self.fields['data_nascimento_fundacao'].required = False
        self.fields['email'].required = True
        for address_field in ('cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf'):
            self.fields[address_field].required = False
        self.fields['uf'].widget.attrs['maxlength'] = 2
        self.fields['uf'].widget.attrs['placeholder'] = 'SP'
        self.fields['data_nascimento_fundacao'].widget.attrs.update({
            'placeholder': today,
            'title': f'Exemplo: {today}',
        })
        self.fields['cep'].widget.attrs.update({
            'placeholder': '00000-000',
            'maxlength': 9,
            'inputmode': 'numeric',
            'data-mask': 'cep',
        })
        self.fields['documento'].widget.attrs.update({
            'placeholder': '000.000.000-00',
            'maxlength': 18,
            'inputmode': 'numeric',
            'data-mask': 'documento',
        })
        self.fields['whatsapp'].widget.attrs.update({
            'placeholder': '(00) 00000-0000',
            'maxlength': 15,
            'inputmode': 'numeric',
            'data-mask': 'telefone',
        })
        self.fields['email'].widget.attrs.update({
            'placeholder': 'nome@email.com',
            'autocomplete': 'email',
        })

    def clean_email(self):
        return normalize_email(self.cleaned_data.get('email'))

    def clean_whatsapp(self):
        whatsapp = format_phone(self.cleaned_data.get('whatsapp'))
        digits = only_digits(whatsapp)

        if len(digits) not in (10, 11):
            raise forms.ValidationError('Informe um telefone/WhatsApp válido com DDD.')

        return whatsapp

    def clean_cep(self):
        cep = format_cep(self.cleaned_data.get('cep'))
        digits = only_digits(cep)

        if not digits:
            return ''

        if len(digits) != 8:
            raise forms.ValidationError('CEP deve conter 8 dígitos.')

        return cep

    def clean_uf(self):
        return (self.cleaned_data.get('uf') or '').strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        tipo_pessoa = cleaned_data.get('tipo_pessoa')
        documento = cleaned_data.get('documento')

        if documento:
            digits = only_digits(documento)
            if tipo_pessoa == PessoaTipo.FISICA:
                if len(digits) != 11:
                    self.add_error('documento', 'CPF deve conter 11 dígitos.')
                else:
                    cleaned_data['documento'] = format_cpf(digits)
            elif tipo_pessoa == PessoaTipo.JURIDICA:
                if len(digits) != 14:
                    self.add_error('documento', 'CNPJ deve conter 14 dígitos.')
                else:
                    cleaned_data['documento'] = format_cnpj(digits)
        else:
            cleaned_data['documento'] = None

        self.validate_document_uniqueness(cleaned_data)
        self.validate_contact_uniqueness(cleaned_data)
        return cleaned_data

    def get_duplicate_queryset(self, model, **filters):
        queryset = model.objects.filter(**filters)
        if model == self._meta.model and self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        return queryset

    def get_duplicate_label(self, obj):
        return 'cliente' if isinstance(obj, Customer) else 'fornecedor'

    def validate_document_uniqueness(self, cleaned_data):
        documento = cleaned_data.get('documento')
        if not documento:
            return

        for model in self.duplicate_models:
            duplicate = self.get_duplicate_queryset(model, documento=documento).first()
            if duplicate:
                label = self.get_duplicate_label(duplicate)
                message = f'Já existe {label} cadastrado com este documento: {duplicate.nome_razao_social}.'
                self.add_error('documento', message)
                self.add_error(None, message)
                return

    def validate_contact_uniqueness(self, cleaned_data):
        email = cleaned_data.get('email')
        whatsapp = cleaned_data.get('whatsapp')
        model = self._meta.model

        if email:
            duplicate = self.get_duplicate_queryset(model, email__iexact=email).first()
            if duplicate:
                label = self.get_duplicate_label(duplicate)
                message = f'Já existe {label} cadastrado com este email: {duplicate.nome_razao_social}.'
                self.add_error('email', message)
                self.add_error(None, message)

        if whatsapp:
            phone_candidates = {whatsapp, only_digits(whatsapp), format_phone(whatsapp)}
            duplicate = self.get_duplicate_queryset(model, whatsapp__in=phone_candidates).first()
            if duplicate:
                label = self.get_duplicate_label(duplicate)
                message = f'Já existe {label} cadastrado com este telefone/WhatsApp: {duplicate.nome_razao_social}.'
                self.add_error('whatsapp', message)
                self.add_error(None, message)


class CustomerForm(PessoaFormMixin, forms.ModelForm):
    default_tipo_pessoa = PessoaTipo.FISICA

    class Meta:
        model = Customer
        fields = PessoaFormMixin.fields
        widgets = {
            'data_nascimento_fundacao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'categorias': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_nascimento_fundacao'].input_formats = DATE_INPUT_FORMATS
        self.fields['categorias'].queryset = Category.objects.filter(
            aplicacao=CategoryAudience.CLIENTE,
            ativa=True,
            excluido_em__isnull=True,
        )


class SupplierForm(PessoaFormMixin, forms.ModelForm):
    default_tipo_pessoa = PessoaTipo.JURIDICA

    class Meta:
        model = Supplier
        fields = PessoaFormMixin.fields
        widgets = {
            'data_nascimento_fundacao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'categorias': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_nascimento_fundacao'].input_formats = DATE_INPUT_FORMATS
        self.fields['categorias'].queryset = Category.objects.filter(
            aplicacao=CategoryAudience.FORNECEDOR,
            ativa=True,
            excluido_em__isnull=True,
        )


class CategoryForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['nome', 'aplicacao']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()


class VehicleForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'cliente',
            'placa',
            'fipe_tipo',
            'fipe_marca_codigo',
            'fipe_modelo_codigo',
            'fipe_ano_codigo',
            'codigo_fipe',
            'mes_referencia_fipe',
            'marca',
            'modelo',
            'versao',
            'qtd_portas',
            'combustivel',
            'km',
            'chassi',
            'tipo_direcao',
            'ar_condicionado',
            'modificado',
            'observacao',
        ]
        widgets = {
            'fipe_marca_codigo': forms.HiddenInput(),
            'fipe_modelo_codigo': forms.HiddenInput(),
            'fipe_ano_codigo': forms.HiddenInput(),
            'codigo_fipe': forms.HiddenInput(),
            'mes_referencia_fipe': forms.HiddenInput(),
            'observacao': forms.Textarea(attrs={'rows': 4}),
            'marca': forms.TextInput(attrs={'data-fipe-brand-name': 'true'}),
            'modelo': forms.TextInput(attrs={'data-fipe-model-name': 'true'}),
            'versao': forms.TextInput(attrs={'data-fipe-version-name': 'true'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['cliente'].queryset = Customer.objects.order_by('nome_razao_social', 'pk')
        self.fields['cliente'].empty_label = 'Selecione o cliente'
        self.fields['fipe_tipo'].initial = self.fields['fipe_tipo'].initial or VehicleFipeType.CARRO
        self.fields['qtd_portas'].required = False
        self.fields['combustivel'].required = False
        self.fields['tipo_direcao'].required = False
        self.fields['versao'].required = False
        self.fields['observacao'].required = False
        self.fields['chassi'].required = False
        self.fields['km'].initial = self.initial.get('km', getattr(self.instance, 'km', 0) or 0)
        self.fields['placa'].widget.attrs.update({
            'placeholder': 'ABC-1234 ou ABC1D23',
            'maxlength': '8',
            'data-mask': 'placa',
            'autocomplete': 'off',
        })
        self.fields['marca'].widget.attrs.update({'placeholder': 'Preenchida pela consulta FIPE ou manualmente'})
        self.fields['modelo'].widget.attrs.update({'placeholder': 'Preenchido pela consulta FIPE ou manualmente'})
        self.fields['versao'].widget.attrs.update({'placeholder': 'Ano/versão FIPE ou versão manual'})
        self.fields['qtd_portas'].widget.attrs.update({'min': '0', 'max': '9', 'step': '1', 'placeholder': '4', 'inputmode': 'numeric'})
        self.fields['km'].widget.attrs.update({'min': '0', 'step': '1', 'placeholder': '0', 'inputmode': 'numeric'})
        self.fields['chassi'].widget.attrs.update({'maxlength': '17', 'placeholder': '17 caracteres', 'data-mask': 'chassi'})
        self.fields['fipe_tipo'].widget.attrs.update({'data-fipe-type': 'true'})

    def clean_placa(self):
        placa = format_plate(self.cleaned_data.get('placa'))
        raw = only_alnum_upper(placa)
        if len(raw) != 7:
            raise forms.ValidationError('Informe uma placa válida com 7 caracteres.')
        return placa

    def clean_chassi(self):
        chassi = only_alnum_upper(self.cleaned_data.get('chassi'))
        if chassi and len(chassi) != 17:
            raise forms.ValidationError('Chassi deve conter 17 caracteres.')
        return chassi

    def clean(self):
        cleaned_data = super().clean()
        placa = cleaned_data.get('placa')
        if placa:
            queryset = Vehicle.objects.filter(placa=placa)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            duplicate = queryset.first()
            if duplicate:
                self.add_error('placa', f'Já existe veículo ativo com esta placa: {duplicate}.')
        return cleaned_data
