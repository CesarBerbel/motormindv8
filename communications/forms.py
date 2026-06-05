from django import forms
from django.forms import modelformset_factory
from django.db.models import Q

from core.forms import BASE_CHECKBOX_CLASS, BASE_INPUT_CLASS, BASE_MULTISELECT_CLASS, BASE_SELECT_CLASS
from core.models import Category, CategoryAudience, Customer, Supplier
from .models import MessageSettings, MessageTemplate, MessageTemplateType, RecipientKind, WorkOrderStatusMessageRule
from .services import Recipient


BASE_TEXTAREA_CLASS = 'textarea textarea-bordered min-h-48 w-full'


class MessageSettingsForm(forms.ModelForm):
    class Meta:
        model = MessageSettings
        fields = [
            'enviar_aniversario_pessoa_fisica',
            'enviar_fundacao_pessoa_juridica',
            'enviar_status_os',
            'template_orcamento_os',
        ]
        widgets = {
            'enviar_aniversario_pessoa_fisica': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
            'enviar_fundacao_pessoa_juridica': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
            'enviar_status_os': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
            'template_orcamento_os': forms.Select(attrs={'class': BASE_SELECT_CLASS}),
        }
        help_texts = {
            'enviar_aniversario_pessoa_fisica': 'Controla apenas o envio automático para clientes pessoa física. Pode ficar habilitado ou desabilitado independentemente da pessoa jurídica.',
            'enviar_fundacao_pessoa_juridica': 'Controla apenas o envio automático para clientes pessoa jurídica. Pode ficar habilitado ou desabilitado independentemente da pessoa física.',
            'enviar_status_os': 'Controla a automação de mensagens de OS. As regras individuais por status continuam sendo respeitadas.',
            'template_orcamento_os': 'Template usado no botão Enviar orçamento e no envio automático quando a OS entra em Aguardando aprovação.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template_orcamento_os'].queryset = MessageTemplate.objects.filter(
            tipo=MessageTemplateType.WORK_ORDER_APPROVAL,
        ).order_by('nome')
        self.fields['template_orcamento_os'].empty_label = 'Template padrão de orçamento / aprovação da OS'


class WorkOrderStatusMessageRuleForm(forms.ModelForm):
    class Meta:
        model = WorkOrderStatusMessageRule
        fields = ['enviar_email', 'template']
        widgets = {
            'enviar_email': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
            'template': forms.Select(attrs={'class': BASE_SELECT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template'].queryset = MessageTemplate.objects.filter(
            tipo=MessageTemplateType.WORK_ORDER_STATUS,
        ).order_by('nome')
        self.fields['template'].empty_label = 'Template padrão de mudança de status'


WorkOrderStatusMessageRuleFormSet = modelformset_factory(
    WorkOrderStatusMessageRule,
    form=WorkOrderStatusMessageRuleForm,
    extra=0,
    can_delete=False,
)


class MessageTemplateForm(forms.ModelForm):
    class Meta:
        model = MessageTemplate
        fields = ['nome', 'tipo', 'assunto', 'corpo', 'padrao']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': BASE_INPUT_CLASS,
                'placeholder': 'Ex.: Aniversário pessoa física',
            }),
            'tipo': forms.Select(attrs={'class': BASE_SELECT_CLASS}),
            'assunto': forms.TextInput(attrs={
                'class': BASE_INPUT_CLASS,
                'placeholder': 'Ex.: Feliz aniversário, {{ nome }}!',
            }),
            'corpo': forms.Textarea(attrs={
                'class': BASE_TEXTAREA_CLASS,
                'placeholder': 'Use variáveis como {{ nome }}, {{ cliente.nome_razao_social }}, {{ fornecedor.nome_razao_social }} e {{ data_envio }}.',
            }),
            'padrao': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
        }
        help_texts = {
            'tipo': 'Templates de aniversário/fundação, mudança de status e orçamento/aprovação da OS são usados em automações. Templates Manual / Outro podem ser usados em mensagens manuais.',
            'padrao': 'Para aniversário/fundação, o envio automático usa o template padrão do tipo correspondente.',
            'corpo': 'O corpo aceita HTML simples e variáveis de template do Django.',
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            if instance.padrao and instance.excluido_em is None:
                MessageTemplate.all_objects.filter(
                    tipo=instance.tipo,
                    padrao=True,
                    excluido_em__isnull=True,
                ).exclude(pk=instance.pk).update(padrao=False)
            instance.save()
            self.save_m2m()
        return instance


class ManualMessageForm(forms.Form):
    enviar_para_todos = forms.BooleanField(
        label='Enviar para todos os clientes e fornecedores ativos',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
    )
    somente_aceita_marketing = forms.BooleanField(
        label='Enviar somente para contatos que aceitam marketing',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
    )
    clientes = forms.ModelMultipleChoiceField(
        label='Clientes específicos',
        queryset=Customer.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': BASE_MULTISELECT_CLASS}),
    )
    fornecedores = forms.ModelMultipleChoiceField(
        label='Fornecedores específicos',
        queryset=Supplier.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': BASE_MULTISELECT_CLASS}),
    )
    categorias_clientes = forms.ModelMultipleChoiceField(
        label='Categorias de clientes',
        queryset=Category.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': BASE_MULTISELECT_CLASS}),
    )
    categorias_fornecedores = forms.ModelMultipleChoiceField(
        label='Categorias de fornecedores',
        queryset=Category.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': BASE_MULTISELECT_CLASS}),
    )
    template = forms.ModelChoiceField(
        label='Template',
        queryset=MessageTemplate.objects.none(),
        required=False,
        empty_label='Sem template',
        widget=forms.Select(attrs={'class': BASE_SELECT_CLASS}),
    )
    assunto = forms.CharField(
        label='Assunto',
        max_length=180,
        required=False,
        widget=forms.TextInput(attrs={
            'class': BASE_INPUT_CLASS,
            'placeholder': 'Assunto do email',
        }),
    )
    corpo = forms.CharField(
        label='Mensagem',
        required=False,
        widget=forms.Textarea(attrs={
            'class': BASE_TEXTAREA_CLASS,
            'placeholder': 'Escreva o conteúdo do email aqui ou selecione um template.',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['clientes'].queryset = Customer.objects.order_by('nome_razao_social')
        self.fields['fornecedores'].queryset = Supplier.objects.order_by('nome_razao_social')
        self.fields['categorias_clientes'].queryset = Category.objects.filter(
            aplicacao=CategoryAudience.CLIENTE,
            ativa=True,
            excluido_em__isnull=True,
        ).order_by('nome')
        self.fields['categorias_fornecedores'].queryset = Category.objects.filter(
            aplicacao=CategoryAudience.FORNECEDOR,
            ativa=True,
            excluido_em__isnull=True,
        ).order_by('nome')
        self.fields['template'].queryset = MessageTemplate.objects.filter(
            tipo__in=[
                MessageTemplateType.MANUAL,
                MessageTemplateType.CUSTOMER_BIRTHDAY_PHYSICAL,
                MessageTemplateType.CUSTOMER_FOUNDATION_LEGAL,
            ]
        ).order_by('tipo', 'nome')

    def clean(self):
        cleaned_data = super().clean()
        has_any_target = any([
            cleaned_data.get('enviar_para_todos'),
            cleaned_data.get('clientes'),
            cleaned_data.get('fornecedores'),
            cleaned_data.get('categorias_clientes'),
            cleaned_data.get('categorias_fornecedores'),
        ])
        if not has_any_target:
            raise forms.ValidationError('Selecione pelo menos um destinatário, uma categoria ou marque enviar para todos.')

        template = cleaned_data.get('template')
        assunto = (cleaned_data.get('assunto') or '').strip()
        corpo = (cleaned_data.get('corpo') or '').strip()

        if not template and not assunto:
            self.add_error('assunto', 'Informe o assunto ou selecione um template.')
        if not template and not corpo:
            self.add_error('corpo', 'Informe a mensagem ou selecione um template.')

        return cleaned_data

    def _apply_marketing_filter(self, queryset):
        if self.cleaned_data.get('somente_aceita_marketing'):
            queryset = queryset.filter(aceita_marketing=True)
        return queryset

    def get_customer_queryset(self):
        queryset = Customer.objects.none()
        if self.cleaned_data.get('enviar_para_todos'):
            queryset = Customer.objects.all()
        else:
            customer_ids = [customer.pk for customer in self.cleaned_data.get('clientes', [])]
            customer_category_ids = [category.pk for category in self.cleaned_data.get('categorias_clientes', [])]
            filters = Q()
            if customer_ids:
                filters |= Q(pk__in=customer_ids)
            if customer_category_ids:
                filters |= Q(categorias__in=customer_category_ids)
            if filters:
                queryset = Customer.objects.filter(filters)

        return self._apply_marketing_filter(queryset).exclude(email='').distinct().order_by('nome_razao_social')

    def get_supplier_queryset(self):
        queryset = Supplier.objects.none()
        if self.cleaned_data.get('enviar_para_todos'):
            queryset = Supplier.objects.all()
        else:
            supplier_ids = [supplier.pk for supplier in self.cleaned_data.get('fornecedores', [])]
            supplier_category_ids = [category.pk for category in self.cleaned_data.get('categorias_fornecedores', [])]
            filters = Q()
            if supplier_ids:
                filters |= Q(pk__in=supplier_ids)
            if supplier_category_ids:
                filters |= Q(categorias__in=supplier_category_ids)
            if filters:
                queryset = Supplier.objects.filter(filters)

        return self._apply_marketing_filter(queryset).exclude(email='').distinct().order_by('nome_razao_social')

    def get_recipients(self):
        recipients = []
        seen = set()

        for customer in self.get_customer_queryset():
            key = (RecipientKind.CUSTOMER, customer.pk)
            if key not in seen:
                seen.add(key)
                recipients.append(Recipient(kind=RecipientKind.CUSTOMER, obj=customer))

        for supplier in self.get_supplier_queryset():
            key = (RecipientKind.SUPPLIER, supplier.pk)
            if key not in seen:
                seen.add(key)
                recipients.append(Recipient(kind=RecipientKind.SUPPLIER, obj=supplier))

        return recipients
