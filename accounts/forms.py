from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from accounts.models import UserProfile
from industries.models import Industry

User = get_user_model()


def _field_attrs(placeholder):
    return {
        'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10',
        'placeholder': placeholder,
    }


def normalize_uz_phone(value):
    digits = ''.join(ch for ch in (value or '') if ch.isdigit())
    if digits.startswith('998'):
        digits = digits[3:]
    if len(digits) != 9:
        raise ValidationError("Telefon raqam 9 ta raqamdan iborat bo'lishi kerak.")
    return f'+998{digits}'


def phone_widget_attrs(placeholder='90 123 45 67'):
    attrs = _field_attrs(placeholder)
    attrs.update(
        {
            'inputmode': 'numeric',
            'autocomplete': 'tel-national',
            'maxlength': '12',
            'data-phone-input': 'uz',
            'class': attrs['class'] + ' pl-[4.75rem]',
        }
    )
    return attrs


class SafeWorkAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Telefon raqam', widget=forms.TextInput(attrs={**phone_widget_attrs(), 'autofocus': True}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={**_field_attrs('Parolni kiriting'), 'id': 'pw-field', 'class': _field_attrs('Parolni kiriting')['class'] + ' pr-12'})
    )

    error_messages = {
        'invalid_login': "Telefon raqam yoki parol noto'g'ri.",
        'inactive': "Ushbu akkaunt bloklangan.",
    }

    def clean(self):
        phone = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if phone and password:
            normalized_phone = normalize_uz_phone(phone)
            self.cleaned_data['username'] = normalized_phone
            self.user_cache = authenticate(self.request, username=normalized_phone, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError("Ushbu akkaunt bloklangan. Tizim mas'uli bilan bog'laning.", code='inactive')
        super().confirm_login_allowed(user)


class BaseRegistrationForm(UserCreationForm):
    error_messages = {
        'password_mismatch': "Parollar bir xil bo'lishi kerak.",
    }

    full_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs=_field_attrs("To'liq ism")))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs=_field_attrs('Email')))
    username = forms.CharField(label='Telefon raqam', widget=forms.TextInput(attrs=phone_widget_attrs()))
    organization_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs=_field_attrs('Tashkilot nomi')))
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                **_field_attrs('Manzil'),
                'rows': 3,
            }
        ),
    )
    industry = forms.ModelChoiceField(
        queryset=Industry.objects.order_by('name'),
        empty_label='Sohani tanlang',
        widget=forms.Select(
            attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10',
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'full_name', 'email', 'organization_name', 'address', 'industry')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(phone_widget_attrs())
        self.fields['password1'].widget.attrs.update(_field_attrs('Parol'))
        self.fields['password2'].widget.attrs.update(_field_attrs('Parolni tasdiqlang'))
        self.fields['password1'].label = 'Parol'
        self.fields['password2'].label = 'Parolni tasdiqlang'
        self.fields['password1'].help_text = "Kamida 6 ta belgi kiriting."
        self.fields['password2'].help_text = ''

        for field in self.fields.values():
            field.error_messages['required'] = "Bu maydonni to'ldiring."

        self.fields['email'].error_messages['invalid'] = "Email manzil noto'g'ri kiritildi."
        self.fields['password1'].error_messages['required'] = "Parolni kiriting."
        self.fields['password2'].error_messages['required'] = "Parolni tasdiqlang."

    def clean_username(self):
        phone = normalize_uz_phone(self.cleaned_data['username'])
        if User.objects.filter(username=phone).exists():
            raise ValidationError("Bu telefon raqam allaqachon ro'yxatdan o'tgan.")
        if UserProfile.objects.filter(phone_number=phone).exists():
            raise ValidationError("Bu telefon raqam allaqachon ro'yxatdan o'tgan.")
        return phone

    def clean_password1(self):
        password = self.cleaned_data.get('password1', '')
        if len(password) < 6:
            raise ValidationError("Parol kamida 6 ta belgidan iborat bo'lishi kerak.")
        return password


class OrganizationLeaderSignUpForm(BaseRegistrationForm):
    class Meta(BaseRegistrationForm.Meta):
        fields = BaseRegistrationForm.Meta.fields

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '')
        user.username = self.cleaned_data['username']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=UserProfile.ROLE_ORG_LEADER,
                full_name=self.cleaned_data['full_name'],
                phone_number=self.cleaned_data['username'],
                organization_name=self.cleaned_data['organization_name'],
                address=self.cleaned_data.get('address', ''),
                industry=self.cleaned_data['industry'],
                is_new_registration=True,
            )
        return user


class WorkerSignUpForm(BaseRegistrationForm):
    position = forms.CharField(max_length=255, widget=forms.TextInput(attrs=_field_attrs('Lavozim yoki kasb')))

    class Meta(BaseRegistrationForm.Meta):
        fields = BaseRegistrationForm.Meta.fields + ('position',)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '')
        user.username = self.cleaned_data['username']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=UserProfile.ROLE_WORKER,
                full_name=self.cleaned_data['full_name'],
                phone_number=self.cleaned_data['username'],
                organization_name=self.cleaned_data['organization_name'],
                position=self.cleaned_data['position'],
                address=self.cleaned_data.get('address', ''),
                industry=self.cleaned_data['industry'],
            )
        return user
