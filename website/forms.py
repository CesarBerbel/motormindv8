from django import forms

from core.forms import BASE_INPUT_CLASS, BASE_SELECT_CLASS, format_phone
from .models import Lead, PublicService

BASE_TEXTAREA_CLASS = 'textarea textarea-bordered min-h-32 w-full'


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['nome', 'telefone', 'email', 'veiculo', 'placa', 'servico', 'mensagem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Seu nome'}),
            'telefone': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': '(11) 90000-0000'}),
            'email': forms.EmailInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'seu@email.com (opcional)'}),
            'veiculo': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Ex.: Fiat Uno 2015'}),
            'placa': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'ABC1D23 (opcional)'}),
            'servico': forms.Select(attrs={'class': BASE_SELECT_CLASS}),
            'mensagem': forms.Textarea(attrs={
                'class': BASE_TEXTAREA_CLASS,
                'placeholder': 'Descreva o problema ou o serviço que precisa.',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['servico'].queryset = PublicService.objects.filter(ativo=True).order_by('ordem', 'titulo')
        self.fields['servico'].empty_label = 'Não sei / outro'
        self.fields['email'].required = False
        self.fields['veiculo'].required = False
        self.fields['placa'].required = False
        self.fields['servico'].required = False
        self.fields['mensagem'].required = False

    def clean_telefone(self):
        telefone = (self.cleaned_data.get('telefone') or '').strip()
        return format_phone(telefone) or telefone

    def clean_placa(self):
        return (self.cleaned_data.get('placa') or '').strip().upper()
