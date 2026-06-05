from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    ReadOnlyPasswordHashField,
    SetPasswordForm,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from core.forms import BASE_CHECKBOX_CLASS, BASE_INPUT_CLASS, DaisyFormMixin
from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'autofocus': True,
            'autocomplete': 'email',
            'class': BASE_INPUT_CLASS,
            'placeholder': 'voce@empresa.com',
        }),
    )
    password = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'class': BASE_INPUT_CLASS,
            'placeholder': 'Sua senha',
        }),
    )


def validate_password_for_user(password, user):
    try:
        validate_password(password, user)
    except ValidationError as exc:
        raise forms.ValidationError(exc.messages)


class StyledPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label='Email',
        max_length=254,
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email',
            'class': BASE_INPUT_CLASS,
            'placeholder': 'voce@empresa.com',
        }),
    )


class StyledSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label='Nova senha',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': BASE_INPUT_CLASS,
        }),
        help_text='Use uma senha forte, diferente de dados pessoais e senhas comuns.',
    )
    new_password2 = forms.CharField(
        label='Confirme a nova senha',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': BASE_INPUT_CLASS,
        }),
    )


class StyledPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label='Senha atual',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'class': BASE_INPUT_CLASS,
        }),
    )
    new_password1 = forms.CharField(
        label='Nova senha',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': BASE_INPUT_CLASS,
        }),
        help_text='Use uma senha forte, diferente de dados pessoais e senhas comuns.',
    )
    new_password2 = forms.CharField(
        label='Confirme a nova senha',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': BASE_INPUT_CLASS,
        }),
    )


class UserAdminCreationForm(forms.ModelForm):
    password1 = forms.CharField(label='Senha', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmação de senha', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'nome_razao_social', 'role', 'tipo_pessoa')

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('As senhas não conferem.')

        if password2:
            user = User(
                email=self.cleaned_data.get('email') or '',
                nome_razao_social=self.cleaned_data.get('nome_razao_social') or '',
                role=self.cleaned_data.get('role') or User._meta.get_field('role').default,
                tipo_pessoa=self.cleaned_data.get('tipo_pessoa') or User._meta.get_field('tipo_pessoa').default,
            )
            validate_password_for_user(password2, user)

        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class UserAdminChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label='Senha')

    class Meta:
        model = User
        fields = '__all__'


class EmployeeBaseForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'email',
            'role',
            'is_active',
            'tipo_pessoa',
            'nome_razao_social',
            'documento',
            'data_nascimento_fundacao',
            'whatsapp',
            'cep',
            'logradouro',
            'numero',
            'complemento',
            'bairro',
            'cidade',
            'uf',
            'aceita_marketing',
        ]
        widgets = {
            'data_nascimento_fundacao': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_daisy_classes()
        self.fields['email'].widget.attrs.update({'autocomplete': 'email'})
        self.fields['is_active'].widget.attrs['class'] = BASE_CHECKBOX_CLASS
        self.fields['uf'].widget.attrs['maxlength'] = 2
        self.fields['uf'].widget.attrs['placeholder'] = 'SP'
        self.fields['cep'].widget.attrs['placeholder'] = '00000-000'
        self.fields['whatsapp'].widget.attrs['placeholder'] = '(00) 00000-0000'

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()


class EmployeeCreateForm(EmployeeBaseForm):
    password1 = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': BASE_INPUT_CLASS, 'autocomplete': 'new-password'}),
        help_text='Use uma senha forte, diferente de dados pessoais e senhas comuns.',
    )
    password2 = forms.CharField(
        label='Confirme a senha',
        widget=forms.PasswordInput(attrs={'class': BASE_INPUT_CLASS, 'autocomplete': 'new-password'}),
    )

    class Meta(EmployeeBaseForm.Meta):
        fields = EmployeeBaseForm.Meta.fields + ['password1', 'password2']

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('As senhas não conferem.')

        if password2:
            user = User(
                email=self.cleaned_data.get('email') or '',
                nome_razao_social=self.cleaned_data.get('nome_razao_social') or '',
                role=self.cleaned_data.get('role') or User._meta.get_field('role').default,
                tipo_pessoa=self.cleaned_data.get('tipo_pessoa') or User._meta.get_field('tipo_pessoa').default,
            )
            validate_password_for_user(password2, user)

        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        user.set_password(self.cleaned_data['password1'])

        if commit:
            user.save()
            self.save_m2m()

        return user


class EmployeeUpdateForm(EmployeeBaseForm):
    nova_senha = forms.CharField(
        label='Nova senha',
        required=False,
        widget=forms.PasswordInput(attrs={'class': BASE_INPUT_CLASS, 'autocomplete': 'new-password'}),
        help_text='Deixe em branco para manter a senha atual. Ao informar uma nova senha, ela precisa atender à política de segurança.',
    )

    class Meta(EmployeeBaseForm.Meta):
        fields = EmployeeBaseForm.Meta.fields + ['nova_senha']

    def clean_nova_senha(self):
        nova_senha = self.cleaned_data.get('nova_senha')
        if nova_senha:
            validate_password_for_user(nova_senha, self.instance)
        return nova_senha

    def save(self, commit=True):
        user = super().save(commit=False)
        nova_senha = self.cleaned_data.get('nova_senha')

        if nova_senha:
            user.set_password(nova_senha)

        user.is_staff = False
        user.is_superuser = False

        if commit:
            user.save()
            self.save_m2m()

        return user
