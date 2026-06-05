from datetime import timedelta

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone
from django.db.models.functions import Lower

from core.models import Customer, Vehicle

from core.forms import BASE_INPUT_CLASS, BASE_SELECT_CLASS, DaisyFormMixin
from core.money import MoneyFormField, normalize_money
from stock.models import InventoryItem, MIN_QUANTITY

MAX_CHECKIN_PHOTO_SIZE_BYTES = 8 * 1024 * 1024
ALLOWED_CHECKIN_PHOTO_TYPES = {'image/jpeg', 'image/png', 'image/webp'}

from .models import (
    Service,
    ServiceCategory,
    ServiceCombo,
    ServiceComboItem,
    ServiceDefaultPart,
    WorkOrder,
    WorkOrderSettings,
    WorkOrderStatus,
    WorkOrderComboItem,
    WorkOrderPartItem,
    WorkOrderServiceItem,
    WorkOrderApprovalBudgetItem,
    WorkOrderApprovalDecision,
    WorkOrderApprovalMethod,
    PdfSettings,
    PdfTemplateSettings,
)

QUANTITY_INPUT_CLASS = 'input input-bordered w-full'



class ServiceCategoryForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = ['nome', 'descricao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['descricao'].required = False


class ServiceForm(DaisyFormMixin, forms.ModelForm):
    valor = MoneyFormField(label='Valor')

    class Meta:
        model = Service
        fields = ['nome', 'categoria', 'descricao', 'duracao_minutos', 'valor']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'duracao_minutos': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['categoria'].queryset = ServiceCategory.objects.order_by(Lower('nome'), 'pk')
        self.fields['categoria'].required = False
        self.fields['descricao'].required = False
        self.fields['duracao_minutos'].widget.attrs.update({
            'placeholder': '60',
            'inputmode': 'numeric',
        })

    def clean_duracao_minutos(self):
        value = self.cleaned_data.get('duracao_minutos')
        if value is None or value < 1:
            raise forms.ValidationError('Informe uma duração maior que zero.')
        return value


class ServiceDefaultPartForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceDefaultPart
        fields = ['item', 'quantidade', 'observacao']
        widgets = {
            'quantidade': forms.NumberInput(attrs={'step': '1', 'min': '1'}),
            'observacao': forms.TextInput(),
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
        self.fields['quantidade'].required = False
        self.fields['observacao'].required = False
        if not self.instance.pk:
            self.fields['quantidade'].initial = None

    def clean_quantidade(self):
        value = self.cleaned_data.get('quantidade')
        if value is None:
            return value
        if value < MIN_QUANTITY:
            raise forms.ValidationError('Informe uma quantidade inteira maior que zero.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        quantidade = cleaned_data.get('quantidade')

        if item and quantidade is None:
            self.add_error('quantidade', 'Informe a quantidade padrão da peça/insumo.')

        return cleaned_data


class BaseServiceDefaultPartFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()

        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue

            item = form.cleaned_data.get('item')
            if not item:
                continue

            if item.pk in seen:
                form.add_error('item', 'Esta peça/insumo já foi adicionada ao serviço.')
            seen.add(item.pk)


ServiceDefaultPartFormSet = inlineformset_factory(
    Service,
    ServiceDefaultPart,
    form=ServiceDefaultPartForm,
    formset=BaseServiceDefaultPartFormSet,
    extra=1,
    can_delete=True,
)


class PercentageFormField(forms.DecimalField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', 5)
        kwargs.setdefault('decimal_places', 2)
        kwargs.setdefault('min_value', 0)
        kwargs.setdefault('max_value', 100)
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'inputmode': 'decimal',
            'placeholder': '0,00',
        }))
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        return normalize_money(value)


class ServiceComboForm(DaisyFormMixin, forms.ModelForm):
    desconto_percentual = PercentageFormField(label='Desconto percentual')

    class Meta:
        model = ServiceCombo
        fields = ['nome', 'descricao', 'desconto_percentual']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['descricao'].required = False
        self.fields['desconto_percentual'].help_text = 'Opcional. Informe um valor de 0 a 100.'
        self.fields['desconto_percentual'].widget.attrs.update({'data-mask': 'money'})


class ServiceComboItemForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceComboItem
        fields = ['service']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['service'].queryset = Service.objects.order_by(Lower('nome'), 'pk')


class BaseServiceComboItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        active_count = 0

        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue

            service = form.cleaned_data.get('service')
            if not service:
                continue

            active_count += 1
            if service.pk in seen:
                form.add_error('service', 'Este serviço já foi adicionado ao combo.')
            seen.add(service.pk)

        if active_count == 0:
            raise forms.ValidationError('Adicione pelo menos um serviço ao combo.')


ServiceComboItemFormSet = inlineformset_factory(
    ServiceCombo,
    ServiceComboItem,
    form=ServiceComboItemForm,
    formset=BaseServiceComboItemFormSet,
    extra=1,
    can_delete=True,
)


class PdfSettingsForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = PdfSettings
        fields = [
            'logo',
            'cabecalho_global',
            'rodape_global',
            'mostrar_assinatura_cliente_padrao',
            'mostrar_assinatura_oficina_padrao',
        ]
        widgets = {
            'cabecalho_global': forms.Textarea(attrs={'rows': 4}),
            'rodape_global': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['logo'].required = False
        self.fields['logo'].widget.attrs.update({'class': 'file-input file-input-bordered w-full', 'accept': 'image/*'})
        for name in ('cabecalho_global', 'rodape_global'):
            self.fields[name].required = False


class PdfTemplateSettingsForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = PdfTemplateSettings
        fields = [
            'titulo',
            'cabecalho',
            'notas_rodape',
            'mostrar_assinatura_cliente',
            'mostrar_assinatura_oficina',
        ]
        widgets = {
            'cabecalho': forms.Textarea(attrs={'rows': 3}),
            'notas_rodape': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        for name in ('titulo', 'cabecalho', 'notas_rodape'):
            self.fields[name].required = False


class WorkOrderSettingsForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderSettings
        fields = ['prazo_estimativa_dias', 'vagas_oficina']
        widgets = {
            'prazo_estimativa_dias': forms.NumberInput(attrs={
                'min': '0',
                'max': '365',
                'step': '1',
                'placeholder': '7',
                'inputmode': 'numeric',
            }),
            'vagas_oficina': forms.NumberInput(attrs={
                'min': '1',
                'max': '999',
                'step': '1',
                'placeholder': '5',
                'inputmode': 'numeric',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['prazo_estimativa_dias'].help_text = 'Ex.: se informar 7, uma OS criada em 03/06/2026 às 20h terá previsão em 10/06/2026 às 20h.'
        self.fields['vagas_oficina'].help_text = 'Quantidade máxima de veículos/OS ocupando vaga física ao mesmo tempo.'


class WorkOrderForm(DaisyFormMixin, forms.ModelForm):
    desconto_percentual = PercentageFormField(label='Desconto percentual')

    class Meta:
        model = WorkOrder
        fields = [
            'cliente',
            'veiculo',
            'status',
            'previsao_entrega',
            'km_atual',
            'problema_relatado',
            'diagnostico',
            'observacao',
            'desconto_percentual',
        ]
        widgets = {
            'previsao_entrega': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'km_atual': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'problema_relatado': forms.Textarea(attrs={'rows': 4}),
            'diagnostico': forms.Textarea(attrs={'rows': 4}),
            'observacao': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()

        is_existing_order = bool(self.instance and self.instance.pk)
        locked_field_names = ('cliente', 'veiculo', 'km_atual', 'previsao_entrega', 'problema_relatado')

        customer_id = None
        if is_existing_order:
            customer_id = self.instance.cliente_id
        elif self.is_bound:
            customer_id = self.data.get(self.add_prefix('cliente')) or self.data.get('cliente')
        elif self.initial.get('cliente'):
            customer_id = self.initial.get('cliente')

        vehicles_queryset = Vehicle.objects.select_related('cliente').order_by('placa', 'pk')
        if customer_id:
            try:
                vehicles_queryset = vehicles_queryset.filter(cliente_id=int(customer_id))
            except (TypeError, ValueError):
                vehicles_queryset = vehicles_queryset.none()

        self.fields['cliente'].queryset = Customer.objects.order_by('nome_razao_social', 'pk')
        self.fields['veiculo'].queryset = vehicles_queryset
        self.fields['veiculo'].required = False

        if self.instance and self.instance.pk:
            current_status = self.instance.status
            allowed_statuses = [current_status, *self.instance.get_available_transitions()]
            self.fields['status'].choices = [choice for choice in WorkOrderStatus.choices if choice[0] in allowed_statuses]
            self.fields['status'].help_text = 'A máquina de estados permite apenas o status atual e os próximos status válidos.'
            if self.instance.status == WorkOrderStatus.CANCELADA:
                for field in self.fields.values():
                    field.disabled = True
                    field.required = False
                    field.widget.attrs['disabled'] = 'disabled'
                    field.widget.attrs['readonly'] = 'readonly'
                    css_class = field.widget.attrs.get('class', '')
                    if 'opacity-70' not in css_class:
                        field.widget.attrs['class'] = f'{css_class} opacity-70 cursor-not-allowed'.strip()
        else:
            self.fields['status'].initial = WorkOrderStatus.ABERTA
            self.fields['status'].choices = [(WorkOrderStatus.ABERTA, WorkOrderStatus.ABERTA.label)]
            self.fields['status'].help_text = 'Toda OS nova começa como Aberta.'
        self.fields['diagnostico'].required = False
        self.fields['observacao'].required = False
        self.fields['desconto_percentual'].help_text = 'Opcional. Informe um valor de 0 a 100.'
        self.fields['desconto_percentual'].widget.attrs.update({'data-mask': 'money'})
        self.fields['previsao_entrega'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['km_atual'].widget.attrs.update({'placeholder': '0', 'inputmode': 'numeric'})
        self.fields['cliente'].widget.attrs.update({'data-work-order-customer': 'true'})
        self.fields['veiculo'].widget.attrs.update({'data-work-order-vehicle': 'true'})

        if is_existing_order:
            locked_help_text = 'Campo travado após a abertura da OS.'
            for field_name in locked_field_names:
                field = self.fields[field_name]
                field.disabled = True
                field.required = False
                field.help_text = locked_help_text
                field.widget.attrs['disabled'] = 'disabled'
                field.widget.attrs['readonly'] = 'readonly'
                field.widget.attrs['data-locked-after-open'] = 'true'
                css_class = field.widget.attrs.get('class', '')
                if 'opacity-70' not in css_class:
                    field.widget.attrs['class'] = f'{css_class} opacity-70 cursor-not-allowed'.strip()

        if not self.is_bound and not (self.instance and self.instance.pk) and not self.initial.get('previsao_entrega'):
            settings = WorkOrderSettings.get_solo()
            default_delivery = timezone.localtime(timezone.now()) + timedelta(days=settings.prazo_estimativa_dias)
            self.initial['previsao_entrega'] = default_delivery.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        cliente = cleaned_data.get('cliente')
        veiculo = cleaned_data.get('veiculo')
        status = cleaned_data.get('status')
        if cliente and veiculo and veiculo.cliente_id != cliente.pk:
            self.add_error('veiculo', 'O veículo selecionado não pertence ao cliente informado.')

        if self.instance and self.instance.pk:
            original = WorkOrder.all_objects.get(pk=self.instance.pk)
            if original.status == WorkOrderStatus.CANCELADA:
                raise forms.ValidationError('OS cancelada não pode ser editada.')
            cleaned_data['cliente'] = original.cliente
            cleaned_data['veiculo'] = original.veiculo
            cleaned_data['km_atual'] = original.km_atual
            cleaned_data['previsao_entrega'] = original.previsao_entrega
            cleaned_data['problema_relatado'] = original.problema_relatado

            status = cleaned_data.get('status')
            if status and status != original.status:
                if not original.can_transition_to(status):
                    current_label = original.get_status_display()
                    new_label = dict(WorkOrderStatus.choices).get(status, status)
                    self.add_error('status', f'Transição inválida: {current_label} → {new_label}. Use um próximo status permitido pela máquina de estados.')
                elif status == WorkOrderStatus.EM_EXECUCAO and original.has_stock_shortage():
                    self.add_error('status', 'Não é possível mover a OS para Em execução porque há peças sem estoque suficiente.')
        else:
            settings = WorkOrderSettings.get_solo()
            vagas_ocupadas = WorkOrder.workshop_occupied_count()
            if vagas_ocupadas >= settings.vagas_oficina:
                raise forms.ValidationError(
                    f'Capacidade da oficina esgotada: {vagas_ocupadas}/{settings.vagas_oficina} vaga(s) ocupada(s). '
                    'Libere uma vaga concluindo, entregando, cancelando ou arquivando uma OS antes de abrir outra.'
                )
            cleaned_data['status'] = WorkOrderStatus.ABERTA

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.instance and self.instance.pk:
            original = WorkOrder.all_objects.get(pk=self.instance.pk)
            obj.cliente = original.cliente
            obj.veiculo = original.veiculo
            obj.km_atual = original.km_atual
            obj.previsao_entrega = original.previsao_entrega
            obj.problema_relatado = original.problema_relatado
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class WorkOrderServiceItemForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderServiceItem
        fields = ['service', 'quantidade']
        widgets = {'quantidade': forms.NumberInput(attrs={'step': '1', 'min': '1'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['service'].queryset = Service.objects.order_by(Lower('nome'), 'pk')
        self.fields['quantidade'].widget.attrs.update({'class': QUANTITY_INPUT_CLASS, 'placeholder': '1', 'inputmode': 'numeric'})
        self.fields['quantidade'].required = False
        if not self.instance.pk:
            self.fields['quantidade'].initial = None

    def clean_quantidade(self):
        value = self.cleaned_data.get('quantidade')
        if value is None:
            return value
        if value < MIN_QUANTITY:
            raise forms.ValidationError('Informe uma quantidade inteira maior que zero.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get('service')
        quantidade = cleaned_data.get('quantidade')
        if service and quantidade is None:
            self.add_error('quantidade', 'Informe a quantidade do serviço.')
        return cleaned_data


class BaseWorkOrderServiceItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or form.cleaned_data.get('DELETE'):
                continue
            service = form.cleaned_data.get('service')
            if not service:
                continue
            if service.pk in seen:
                form.add_error('service', 'Este serviço já foi adicionado à OS.')
            seen.add(service.pk)


WorkOrderServiceItemFormSet = inlineformset_factory(
    WorkOrder,
    WorkOrderServiceItem,
    form=WorkOrderServiceItemForm,
    formset=BaseWorkOrderServiceItemFormSet,
    extra=1,
    can_delete=True,
)


class WorkOrderComboItemForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderComboItem
        fields = ['combo', 'quantidade']
        widgets = {'quantidade': forms.NumberInput(attrs={'step': '1', 'min': '1'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['combo'].queryset = ServiceCombo.objects.order_by(Lower('nome'), 'pk')
        self.fields['quantidade'].widget.attrs.update({'class': QUANTITY_INPUT_CLASS, 'placeholder': '1', 'inputmode': 'numeric'})
        self.fields['quantidade'].required = False
        if not self.instance.pk:
            self.fields['quantidade'].initial = None

    def clean_quantidade(self):
        value = self.cleaned_data.get('quantidade')
        if value is None:
            return value
        if value < MIN_QUANTITY:
            raise forms.ValidationError('Informe uma quantidade inteira maior que zero.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        combo = cleaned_data.get('combo')
        quantidade = cleaned_data.get('quantidade')
        if combo and quantidade is None:
            self.add_error('quantidade', 'Informe a quantidade do combo.')
        return cleaned_data


class BaseWorkOrderComboItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or form.cleaned_data.get('DELETE'):
                continue
            combo = form.cleaned_data.get('combo')
            if not combo:
                continue
            if combo.pk in seen:
                form.add_error('combo', 'Este combo já foi adicionado à OS.')
            seen.add(combo.pk)


WorkOrderComboItemFormSet = inlineformset_factory(
    WorkOrder,
    WorkOrderComboItem,
    form=WorkOrderComboItemForm,
    formset=BaseWorkOrderComboItemFormSet,
    extra=1,
    can_delete=True,
)


class WorkOrderPartItemForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderPartItem
        fields = ['item', 'quantidade']
        widgets = {'quantidade': forms.NumberInput(attrs={'step': '1', 'min': '1'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['item'].queryset = InventoryItem.objects.select_related('categoria', 'marca', 'unidade').order_by(Lower('nome'), 'pk')
        self.fields['quantidade'].widget.attrs.update({'class': QUANTITY_INPUT_CLASS, 'placeholder': '1', 'inputmode': 'numeric'})
        self.fields['quantidade'].required = False
        if not self.instance.pk:
            self.fields['quantidade'].initial = None

    def clean_quantidade(self):
        value = self.cleaned_data.get('quantidade')
        if value is None:
            return value
        if value < MIN_QUANTITY:
            raise forms.ValidationError('Informe uma quantidade inteira maior que zero.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        quantidade = cleaned_data.get('quantidade')
        if item and quantidade is None:
            self.add_error('quantidade', 'Informe a quantidade da peça/insumo.')
        return cleaned_data


class BaseWorkOrderPartItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or form.cleaned_data.get('DELETE'):
                continue
            item = form.cleaned_data.get('item')
            if not item:
                continue
            if item.pk in seen:
                form.add_error('item', 'Esta peça/insumo já foi adicionada à OS.')
            seen.add(item.pk)


WorkOrderPartItemFormSet = inlineformset_factory(
    WorkOrder,
    WorkOrderPartItem,
    form=WorkOrderPartItemForm,
    formset=BaseWorkOrderPartItemFormSet,
    extra=1,
    can_delete=True,
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        value = files.get(name)
        if value in (None, ''):
            return []
        return value if isinstance(value, (list, tuple)) else [value]


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={
            'class': 'file-input file-input-bordered w-full',
            'accept': 'image/*',
            'capture': 'environment',
            'multiple': True,
        }))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        if data:
            return [single_file_clean(data, initial)]
        return []


from .models import VehicleCheckIn, VehicleCheckInPhoto


class VehicleCheckInForm(DaisyFormMixin, forms.ModelForm):
    fotos = MultipleFileField(
        label='Fotos do veículo',
        required=False,
        help_text='Use no celular/tablet para fotografar diretamente ou selecione uma ou mais imagens.',
    )

    class Meta:
        model = VehicleCheckIn
        fields = [
            'ordem_servico',
            'km',
            'nivel_combustivel',
            'possui_estepe',
            'possui_macaco',
            'possui_chave_roda',
            'possui_documento',
            'objetos_deixados',
            'avarias_observadas',
            'observacoes',
        ]
        widgets = {
            'km': forms.NumberInput(attrs={'min': '0', 'step': '1', 'inputmode': 'numeric'}),
            'objetos_deixados': forms.Textarea(attrs={'rows': 3}),
            'avarias_observadas': forms.Textarea(attrs={'rows': 4}),
            'observacoes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        queryset = WorkOrder.objects.select_related('cliente', 'veiculo').filter(
            ativo=True,
            excluido_em__isnull=True,
            veiculo__isnull=False,
        )
        checked_order_ids = VehicleCheckIn.objects.values_list('ordem_servico_id', flat=True)
        if self.instance.pk and self.instance.ordem_servico_id:
            checked_order_ids = checked_order_ids.exclude(ordem_servico_id=self.instance.ordem_servico_id)
        queryset = queryset.exclude(pk__in=checked_order_ids)
        self.fields['ordem_servico'].queryset = queryset.order_by('-data_abertura', '-pk')
        self.fields['ordem_servico'].label_from_instance = lambda obj: f'{obj.codigo} - {obj.cliente.nome_razao_social} - {obj.veiculo.placa if obj.veiculo else "Sem veículo"}'
        self.fields['km'].required = False
        self.fields['nivel_combustivel'].required = False
        self.fields['objetos_deixados'].required = False
        self.fields['avarias_observadas'].required = False
        self.fields['observacoes'].required = False
        self.fields['fotos'].widget.attrs.update({
            'class': 'file-input file-input-bordered w-full',
            'accept': 'image/*',
            'capture': 'environment',
            'multiple': True,
        })

    def clean_ordem_servico(self):
        ordem_servico = self.cleaned_data.get('ordem_servico')
        if not ordem_servico:
            return ordem_servico
        if not ordem_servico.veiculo_id:
            raise forms.ValidationError('A OS selecionada precisa ter um veículo vinculado para gerar check-in.')
        existing = VehicleCheckIn.objects.filter(ordem_servico=ordem_servico)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError('Esta OS já possui um check-in cadastrado.')
        return ordem_servico

    def clean_fotos(self):
        photos = self.cleaned_data.get('fotos') or []
        errors = []
        for photo in photos:
            if getattr(photo, 'size', 0) > MAX_CHECKIN_PHOTO_SIZE_BYTES:
                errors.append(f'{photo.name}: arquivo maior que 8 MB.')
            content_type = (getattr(photo, 'content_type', '') or '').lower()
            if content_type and content_type not in ALLOWED_CHECKIN_PHOTO_TYPES:
                errors.append(f'{photo.name}: tipo de imagem não permitido. Use JPG, PNG ou WebP.')
        if errors:
            raise forms.ValidationError(errors)
        return photos

    def save_photos(self, checkin):
        for photo in self.cleaned_data.get('fotos') or []:
            VehicleCheckInPhoto.objects.create(checkin=checkin, imagem=photo)


def only_digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def is_valid_cpf(value):
    digits = only_digits(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(digits[index]) * ((size + 1) - index) for index in range(size))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if check != int(digits[size]):
            return False
    return True


def is_valid_cnpj(value):
    digits = only_digits(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    weights = ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    for step in (0, 1):
        total = sum(int(digits[index]) * weights[step][index] for index in range(12 + step))
        remainder = total % 11
        check = 0 if remainder < 2 else 11 - remainder
        if check != int(digits[12 + step]):
            return False
    return True


def is_valid_cpf_or_cnpj(value):
    digits = only_digits(value)
    return is_valid_cpf(digits) if len(digits) == 11 else is_valid_cnpj(digits) if len(digits) == 14 else False


class WorkOrderApprovalDecisionForm(forms.Form):
    decisao = forms.ChoiceField(
        label='Decisão',
        choices=[],
        widget=forms.RadioSelect(attrs={'class': 'radio radio-primary'}),
    )
    metodo = forms.ChoiceField(
        label='Método de aprovação',
        choices=[],
        widget=forms.Select(attrs={'class': BASE_SELECT_CLASS}),
    )
    nome_responsavel = forms.CharField(
        label='Nome do responsável',
        max_length=180,
        widget=forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Nome completo'}),
    )
    documento = forms.CharField(
        label='CPF ou CNPJ válido',
        max_length=20,
        widget=forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'CPF ou CNPJ'}),
    )
    local = forms.CharField(
        label='Local',
        max_length=180,
        required=False,
        widget=forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Ex.: balcão da oficina, WhatsApp, email'}),
    )
    observacao = forms.CharField(
        label='Observação',
        required=True,
        initial='Aprovado',
        widget=forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full', 'rows': 3}),
    )
    assinatura_base64 = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_assinatura_base64'}),
    )
    itens_aprovados = forms.ModelMultipleChoiceField(
        label='Itens aprovados na aprovação parcial',
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox checkbox-primary'}),
    )

    def __init__(self, *args, budget=None, public=False, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import WorkOrderApprovalBudgetItem, WorkOrderApprovalDecision, WorkOrderApprovalMethod
        self.budget = budget
        self.public = public
        self.fields['decisao'].choices = WorkOrderApprovalDecision.choices
        self.fields['metodo'].choices = WorkOrderApprovalMethod.choices
        if public:
            self.fields['metodo'].initial = WorkOrderApprovalMethod.EMAIL
            self.fields['metodo'].widget = forms.HiddenInput()
            self.fields['local'].initial = 'e-mail'
            self.fields['local'].required = False
            self.fields['local'].widget = forms.HiddenInput()
        self.fields['itens_aprovados'].queryset = (
            budget.itens.all().order_by('tipo', 'nome', 'pk') if budget else WorkOrderApprovalBudgetItem.objects.none()
        )
        self.fields['itens_aprovados'].label_from_instance = lambda obj: f'{obj.get_tipo_display()} - {obj.nome} ({obj.quantidade} x {obj.valor_unitario})'

    def clean_documento(self):
        value = self.cleaned_data.get('documento') or ''
        if not is_valid_cpf_or_cnpj(value):
            raise forms.ValidationError('Informe um CPF ou CNPJ válido.')
        return only_digits(value)

    def clean(self):
        cleaned_data = super().clean()
        from .models import WorkOrderApprovalDecision
        decision = cleaned_data.get('decisao')
        approved_items = cleaned_data.get('itens_aprovados')
        if decision == WorkOrderApprovalDecision.APPROVE_PARTIAL and not approved_items:
            self.add_error('itens_aprovados', 'Selecione ao menos um item para aprovação parcial.')
        method = cleaned_data.get('metodo')
        signature = cleaned_data.get('assinatura_base64') or ''
        from .models import WorkOrderApprovalMethod
        if method == WorkOrderApprovalMethod.PRESENTIAL and not signature.startswith('data:image/png;base64,'):
            self.add_error('assinatura_base64', 'Colete a assinatura do cliente para aprovação presencial.')
        return cleaned_data
