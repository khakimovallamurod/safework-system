from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from accounts.models import UserProfile, Region
from companies.models import (
    Department,
    EmployeeMedicalRecord,
    EntryGuideline,
    MandatoryGuideline,
    Section,
    SectionInternalGuideline,
    SectionMembership,
    SectionMessage,
    SectionWorkPractice,
)
from industries.models import Industry
from professions.models import Profession

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
            'class': attrs['class'] + ' pl-[3.65rem]',
        }
    )
    return attrs


class SoplineAuthenticationForm(AuthenticationForm):
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

    last_name = forms.CharField(label='Familya', max_length=255, widget=forms.TextInput(attrs=_field_attrs('Familya')))
    first_name = forms.CharField(label='Ism', max_length=255, widget=forms.TextInput(attrs=_field_attrs('Ism')))
    middle_name = forms.CharField(label='Sharifi', max_length=255, widget=forms.TextInput(attrs=_field_attrs('Sharifi')))
    username = forms.CharField(label='Telefon raqam', widget=forms.TextInput(attrs=phone_widget_attrs()))
    address = forms.CharField(
        label='Manzil',
        widget=forms.Textarea(
            attrs={
                **_field_attrs('Manzil'),
                'rows': 3,
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'middle_name', 'username', 'address')

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

        self.fields['password1'].error_messages['required'] = "Parolni kiriting."
        self.fields['password2'].error_messages['required'] = "Parolni tasdiqlang."

        self.order_fields(['first_name', 'last_name', 'middle_name', 'username', 'address', 'password1', 'password2'])

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

    def build_full_name(self):
        parts = [self.cleaned_data.get('first_name', '').strip(), self.cleaned_data.get('last_name', '').strip(), self.cleaned_data.get('middle_name', '').strip()]
        return ' '.join([part for part in parts if part])


class OrganizationLeaderSignUpForm(BaseRegistrationForm):
    organization_name = forms.CharField(label='Tashkilot nomi', max_length=255, widget=forms.TextInput(attrs=_field_attrs('Tashkilot nomi')))
    industry = forms.ModelChoiceField(
        label='Sohani tanlang',
        queryset=Industry.objects.order_by('name'),
        empty_label='Sohani tanlang',
        widget=forms.Select(
            attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10',
            }
        ),
    )
    region = forms.ModelChoiceField(
        label='Viloyatni tanlang',
        queryset=Region.objects.order_by('name'),
        empty_label='Viloyatni tanlang',
        widget=forms.Select(
            attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10',
            }
        ),
    )

    class Meta(BaseRegistrationForm.Meta):
        fields = ('first_name', 'last_name', 'middle_name', 'username', 'organization_name', 'industry', 'region', 'address')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(['first_name', 'last_name', 'middle_name', 'username', 'organization_name', 'industry', 'region', 'address', 'password1', 'password2'])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=UserProfile.ROLE_ORG_LEADER,
                full_name=self.build_full_name(),
                phone_number=self.cleaned_data['username'],
                organization_name=self.cleaned_data['organization_name'],
                address=self.cleaned_data.get('address', ''),
                industry=self.cleaned_data['industry'],
                region=self.cleaned_data['region'],
                is_new_registration=True,
            )
            profile = user.profile
            profile.organization = profile
            profile.save(update_fields=['organization'])
        return user


class WorkerSignUpForm(BaseRegistrationForm):
    organization = forms.ModelChoiceField(
        label='Tashkilotni tanlang',
        queryset=UserProfile.objects.none(),
        empty_label='Tashkilotni tanlang',
        widget=forms.Select(
            attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10',
            }
        ),
    )
    region = forms.ModelChoiceField(
        label='Viloyatni tanlang',
        queryset=Region.objects.order_by('name'),
        empty_label='Viloyatni tanlang',
        widget=forms.Select(
            attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10',
            }
        ),
    )

    class Meta(BaseRegistrationForm.Meta):
        fields = ('first_name', 'last_name', 'middle_name', 'username', 'organization', 'region', 'address')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['organization'].queryset = (
            UserProfile.objects.filter(role=UserProfile.ROLE_ORG_LEADER)
            .select_related('industry')
            .order_by('organization_name', 'full_name')
        )
        self.fields['organization'].label_from_instance = lambda profile: (
            f"{profile.organization_name or profile.full_name}"
            f"{f' ({profile.industry.name})' if profile.industry else ''}"
        )
        self.order_fields(['first_name', 'last_name', 'middle_name', 'username', 'organization', 'region', 'address', 'password1', 'password2'])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=UserProfile.ROLE_WORKER,
                full_name=self.build_full_name(),
                phone_number=self.cleaned_data['username'],
                organization=self.cleaned_data['organization'],
                organization_name=self.cleaned_data['organization'].organization_name,
                industry=self.cleaned_data['organization'].industry,
                region=self.cleaned_data['region'],
                address=self.cleaned_data.get('address', ''),
            )
        return user


class MandatoryGuidelineForm(forms.ModelForm):
    class Meta:
        model = MandatoryGuideline
        fields = ['guideline_type', 'name', 'pdf_file', 'start_time', 'active_until']
        widgets = {
            'guideline_type': forms.Select(attrs=_field_attrs('Yo‘riqnoma turi')),
            'name': forms.TextInput(attrs=_field_attrs('Yo‘riqnoma nomi')),
            'pdf_file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.docx'}),
            'start_time': forms.DateInput(attrs={**_field_attrs('Boshlanish sanasi'), 'type': 'date'}),
            'active_until': forms.DateInput(attrs={**_field_attrs('Faollik tugashi'), 'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        active_until = cleaned.get('active_until')
        if start and active_until and active_until <= start:
            raise ValidationError("Faollik tugashi boshlanish vaqtidan keyin bo‘lishi kerak.")
        return cleaned


class EmployeeMedicalRecordForm(forms.ModelForm):
    class Meta:
        model = EmployeeMedicalRecord
        fields = ['start_date', 'end_date', 'file', 'note']
        widgets = {
            'start_date': forms.DateInput(attrs={**_field_attrs('Boshlanish sana'), 'type': 'date'}),
            'end_date': forms.DateInput(attrs={**_field_attrs('Tugash sana'), 'type': 'date'}),
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'}),
            'note': forms.Textarea(attrs={**_field_attrs('Izoh'), 'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise ValidationError("Tugash sana boshlanish sanasidan oldin bo'lmasligi kerak.")
        return cleaned


def get_selectable_workers_queryset(
    *,
    include_user_id=None,
    exclude_other_sections=False,
    current_section=None,
    exclude_user_ids=None,
    organization=None,
):
    """
    Bazadagi barcha xodimlar (role=worker).
    exclude_other_sections: boshqa bo'limga biriktirilgan xodimlarni chiqarish (unikallik).
    exclude_user_ids: boshqa boshqarma/bo'limda nazoratchi bo'lgan xodimlar.
    """
    worker_filter = Q(profile__role=UserProfile.ROLE_WORKER)
    choice_filter = worker_filter

    if exclude_other_sections:
        assigned = SectionMembership.objects.all()
        if current_section:
            assigned = assigned.exclude(section=current_section)
        assigned_ids = list(assigned.values_list('user_id', flat=True))
        if assigned_ids:
            choice_filter = worker_filter & ~Q(pk__in=assigned_ids)

    if exclude_user_ids:
        blocked = [uid for uid in exclude_user_ids if uid]
        if blocked:
            choice_filter = choice_filter & ~Q(pk__in=blocked)

    if organization:
        org_name = (organization.organization_name or '').strip()
        org_filter = Q(profile__organization=organization)
        if org_name:
            org_filter |= Q(profile__organization_name=org_name)
        choice_filter = choice_filter & org_filter

    if include_user_id:
        choice_filter = Q(pk=include_user_id) | choice_filter

    queryset = User.objects.filter(is_superuser=False).filter(choice_filter).select_related('profile')
    if include_user_id:
        queryset = queryset.annotate(
            _is_current=models.Case(
                models.When(pk=include_user_id, then=0),
                default=1,
                output_field=models.IntegerField(),
            )
        ).order_by('_is_current', 'profile__full_name', 'username')
    else:
        queryset = queryset.order_by('profile__full_name', 'username')
    return queryset.distinct()


def get_org_leader_workers_queryset(org_leader):
    return get_selectable_workers_queryset(organization=org_leader.profile)


def _org_leader_workers_queryset(org_leader):
    return get_selectable_workers_queryset(organization=org_leader.profile)


def _assigned_department_supervisor_ids(leader_profile, exclude_department=None):
    qs = Department.objects.filter(leader=leader_profile, supervisor__isnull=False)
    if exclude_department:
        qs = qs.exclude(pk=exclude_department.pk)
    return list(qs.values_list('supervisor_id', flat=True))


def get_department_supervisor_choices(org_leader, department=None):
    include_id = department.supervisor_id if department and department.supervisor_id else None
    leader_profile = org_leader.profile
    exclude_ids = _assigned_department_supervisor_ids(leader_profile, exclude_department=department)
    return get_selectable_workers_queryset(
        include_user_id=include_id,
        exclude_user_ids=exclude_ids,
        organization=leader_profile,
    )


def _worker_select_widget(placeholder):
    return forms.Select(
        attrs={
            **_field_attrs(placeholder),
            'class': 'worker-select2 w-full',
        }
    )


class DepartmentCreateForm(forms.Form):
    name = forms.CharField(label="Boshqarma nomi", max_length=255, widget=forms.TextInput(attrs=_field_attrs('Boshqarma nomi')))
    supervisor = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Boshqarma nazoratchisi",
        widget=_worker_select_widget('Nazoratchini tanlang'),
    )

    def __init__(self, *args, **kwargs):
        self.org_leader = kwargs.pop('org_leader', None)
        super().__init__(*args, **kwargs)
        if self.org_leader:
            queryset = _org_leader_workers_queryset(self.org_leader)
            self.fields['supervisor'].queryset = queryset
            self.fields['supervisor'].label_from_instance = lambda user: (
                f"{getattr(user.profile, 'full_name', '') or user.username} ({user.username})"
            )

    def clean_supervisor(self):
        supervisor = self.cleaned_data['supervisor']
        if supervisor.profile.role != UserProfile.ROLE_WORKER:
            raise ValidationError("Faqat xodimlarni boshqarma nazoratchisi sifatida tanlashingiz mumkin.")
        if self.org_leader:
            leader_profile = self.org_leader.profile
            if Department.objects.filter(leader=leader_profile, supervisor=supervisor).exists():
                raise ValidationError("Bu xodim boshqa boshqarmada nazoratchi sifatida biriktirilgan.")
        return supervisor


class DepartmentEditForm(forms.Form):
    name = forms.CharField(label="Boshqarma nomi", max_length=255, widget=forms.TextInput(attrs=_field_attrs('Boshqarma nomi')))
    supervisor = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Boshqarma nazoratchisi",
        widget=_worker_select_widget('Nazoratchini tanlang'),
    )

    def __init__(self, *args, **kwargs):
        self.org_leader = kwargs.pop('org_leader', None)
        self.department = kwargs.pop('department', None)
        super().__init__(*args, **kwargs)
        if self.org_leader:
            self.fields['supervisor'].queryset = get_department_supervisor_choices(self.org_leader, self.department)
            self.fields['supervisor'].label_from_instance = lambda user: (
                f"{getattr(user.profile, 'full_name', '') or user.username} ({user.username})"
            )

    def clean_supervisor(self):
        supervisor = self.cleaned_data['supervisor']
        allowed_roles = {UserProfile.ROLE_WORKER, UserProfile.ROLE_DEPARTMENT_ADMIN}
        if supervisor.profile.role not in allowed_roles:
            raise ValidationError("Faqat xodim yoki joriy nazoratchini tanlashingiz mumkin.")
        if self.org_leader and self.department:
            leader_profile = self.org_leader.profile
            conflict = Department.objects.filter(leader=leader_profile, supervisor=supervisor).exclude(
                pk=self.department.pk
            )
            if conflict.exists():
                raise ValidationError("Bu xodim boshqa boshqarmada nazoratchi sifatida biriktirilgan.")
        return supervisor


def _assigned_section_supervisor_ids(department, exclude_section=None):
    qs = Section.objects.filter(department=department, supervisor__isnull=False)
    if exclude_section:
        qs = qs.exclude(pk=exclude_section.pk)
    return list(qs.values_list('supervisor_id', flat=True))


def get_department_admin_department(dept_admin):
    profile = getattr(dept_admin, 'profile', None)
    if profile is None or not profile.department_id:
        return None
    return profile.department


def _resolve_department_org_name(profile, department):
    org_name = (profile.organization_name or '').strip()
    if not org_name and department and getattr(department, 'leader', None):
        org_name = (department.leader.organization_name or '').strip()
    return org_name


def count_department_team_members(department):
    """Boshqarma ichidagi bo'limlar va xodimlar (unikal foydalanuvchilar)."""
    if not department:
        return 0
    user_ids = set()
    sections = Section.objects.filter(department=department)
    for section in sections:
        if section.supervisor_id:
            user_ids.add(section.supervisor_id)
        user_ids.update(
            SectionMembership.objects.filter(section=section).values_list('user_id', flat=True)
        )
    if department.supervisor_id:
        user_ids.add(department.supervisor_id)
    return len(user_ids)


def get_department_workers_queryset(dept_admin):
    """Boshqarma ichidagi xodimlar — faqat shu boshqarmaga tegishli bo'limlar."""
    department = get_department_admin_department(dept_admin)
    if not department:
        return User.objects.none()
    section_ids = Section.objects.filter(department=department).values_list('pk', flat=True)
    member_ids = SectionMembership.objects.filter(section_id__in=section_ids).values_list('user_id', flat=True)
    supervisor_ids = Section.objects.filter(department=department, supervisor__isnull=False).values_list(
        'supervisor_id', flat=True
    )
    user_ids = set(member_ids) | set(supervisor_ids)
    if not user_ids:
        return User.objects.none()
    return (
        User.objects.filter(pk__in=user_ids, is_superuser=False)
        .select_related('profile')
        .order_by('profile__full_name', 'username')
    )


def get_section_supervisor_choices(dept_admin, section=None):
    include_id = section.supervisor_id if section and section.supervisor_id else None
    department = get_department_admin_department(dept_admin)
    exclude_ids = _assigned_section_supervisor_ids(department, exclude_section=section) if department else []
    return get_selectable_workers_queryset(
        include_user_id=include_id,
        exclude_user_ids=exclude_ids,
        organization=department.leader if department else None,
    )


class SectionCreateForm(forms.Form):
    name = forms.CharField(label="Bo‘lim nomi", max_length=255, widget=forms.TextInput(attrs=_field_attrs('Bo‘lim nomi')))
    profession = forms.ModelChoiceField(
        queryset=Profession.objects.none(),
        label="Kasb",
        widget=forms.Select(attrs=_field_attrs('Kasbni tanlang')),
    )
    supervisor = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Bo‘lim nazoratchisi",
        widget=_worker_select_widget('Nazoratchini tanlang'),
    )

    def __init__(self, *args, **kwargs):
        self.dept_admin = kwargs.pop('dept_admin', None)
        super().__init__(*args, **kwargs)
        if self.dept_admin:
            self.fields['supervisor'].queryset = get_section_supervisor_choices(self.dept_admin)
            self.fields['supervisor'].label_from_instance = lambda user: (
                f"{getattr(user.profile, 'full_name', '') or user.username} ({user.username})"
            )
            department = get_department_admin_department(self.dept_admin)
            if department and department.leader.industry:
                self.fields['profession'].queryset = Profession.objects.filter(industry=department.leader.industry).order_by('name')

    def clean_supervisor(self):
        supervisor = self.cleaned_data['supervisor']
        if supervisor.profile.role != UserProfile.ROLE_WORKER:
            raise ValidationError("Faqat xodimlarni bo‘lim nazoratchisi sifatida tanlashingiz mumkin.")
        if self.dept_admin:
            department = get_department_admin_department(self.dept_admin)
            if department and Section.objects.filter(department=department, supervisor=supervisor).exists():
                raise ValidationError("Bu xodim boshqa bo‘limda nazoratchi sifatida biriktirilgan.")
        return supervisor


class SectionEditForm(forms.Form):
    name = forms.CharField(label="Bo‘lim nomi", max_length=255, widget=forms.TextInput(attrs=_field_attrs('Bo‘lim nomi')))
    profession = forms.ModelChoiceField(
        queryset=Profession.objects.none(),
        label="Kasb",
        widget=forms.Select(attrs=_field_attrs('Kasbni tanlang')),
    )
    supervisor = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Bo‘lim nazoratchisi",
        widget=_worker_select_widget('Nazoratchini tanlang'),
    )

    def __init__(self, *args, **kwargs):
        self.dept_admin = kwargs.pop('dept_admin', None)
        self.section = kwargs.pop('section', None)
        super().__init__(*args, **kwargs)
        if self.dept_admin:
            self.fields['supervisor'].queryset = get_section_supervisor_choices(self.dept_admin, self.section)
            self.fields['supervisor'].label_from_instance = lambda user: (
                f"{getattr(user.profile, 'full_name', '') or user.username} ({user.username})"
            )
            department = get_department_admin_department(self.dept_admin)
            if department and department.leader.industry:
                self.fields['profession'].queryset = Profession.objects.filter(industry=department.leader.industry).order_by('name')
            if self.section and self.section.supervisor:
                membership = SectionMembership.objects.filter(section=self.section, user=self.section.supervisor).first()
                if membership and membership.profession_id:
                    self.fields['profession'].initial = membership.profession_id

    def clean_supervisor(self):
        supervisor = self.cleaned_data['supervisor']
        allowed_roles = {UserProfile.ROLE_WORKER, UserProfile.ROLE_SECTION_ADMIN}
        if supervisor.profile.role not in allowed_roles:
            raise ValidationError("Faqat xodim yoki joriy nazoratchini tanlashingiz mumkin.")
        if self.dept_admin and self.section:
            department = get_department_admin_department(self.dept_admin)
            if (
                department
                and Section.objects.filter(department=department, supervisor=supervisor)
                .exclude(pk=self.section.pk)
                .exists()
            ):
                raise ValidationError("Bu xodim boshqa bo‘limda nazoratchi sifatida biriktirilgan.")
        return supervisor


def get_section_admin_section(section_admin):
    profile = getattr(section_admin, 'profile', None)
    if profile is None or profile.role != UserProfile.ROLE_SECTION_ADMIN or not profile.section_id:
        return None
    return Section.objects.select_related('department', 'department__leader').filter(pk=profile.section_id).first()


def get_section_team_memberships(section):
    return (
        SectionMembership.objects.filter(section=section)
        .select_related('user', 'user__profile', 'section', 'section__department', 'profession')
        .order_by('-assigned_at')
    )


def get_available_section_workers(section):
    """Bo'limga qo'shish: barcha xodimlar, boshqa bo'limda biriktirilmaganlar."""
    return get_selectable_workers_queryset(
        exclude_other_sections=True,
        current_section=section,
        organization=section.department.leader,
    )


def get_section_member_worker_choices(section_admin, membership=None):
    section = get_section_admin_section(section_admin)
    if not section:
        return User.objects.none()
    include_id = membership.user_id if membership else None
    return get_selectable_workers_queryset(
        include_user_id=include_id,
        exclude_other_sections=True,
        current_section=section,
        organization=section.department.leader,
    )


def get_section_member_for_user(user):
    return (
        SectionMembership.objects.filter(user=user)
        .select_related('section', 'section__department', 'section__supervisor', 'section__supervisor__profile')
        .first()
    )


class SectionMessageForm(forms.Form):
    title = forms.CharField(label='Sarlavha', max_length=255, widget=forms.TextInput(attrs=_field_attrs('Xabar sarlavhasi')))
    body = forms.CharField(
        label='Matn',
        widget=forms.Textarea(attrs={**_field_attrs('Xabar matni'), 'rows': 4}),
    )


class SectionMemberAddForm(forms.Form):
    profession = forms.ModelChoiceField(
        queryset=Profession.objects.none(),
        label="Kasb",
        widget=forms.Select(attrs=_field_attrs('Kasbni tanlang')),
    )
    workers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        label="Xodimlar",
        widget=forms.SelectMultiple(
            attrs={
                **_field_attrs('Xodimlarni tanlang'),
                'class': 'worker-select2 w-full',
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        section_admin = kwargs.pop('section_admin', None)
        super().__init__(*args, **kwargs)
        section = get_section_admin_section(section_admin) if section_admin else None
        if section:
            self.fields['profession'].queryset = Profession.objects.filter(
                industry=section.department.leader.industry
            ).order_by('name')
            self.fields['workers'].queryset = get_available_section_workers(section)
            self.fields['workers'].label_from_instance = lambda user: (
                f"{getattr(user.profile, 'full_name', '') or user.username} ({user.username})"
            )

    def clean_workers(self):
        workers = self.cleaned_data['workers']
        if not workers:
            raise ValidationError("Kamida bitta xodimni tanlang.")
        for worker in workers:
            if worker.profile.role != UserProfile.ROLE_WORKER:
                raise ValidationError("Faqat xodimlarni tanlashingiz mumkin.")
        return workers


class SectionMemberEditForm(forms.Form):
    profession = forms.ModelChoiceField(
        queryset=Profession.objects.none(),
        label="Kasb",
        widget=forms.Select(attrs=_field_attrs('Kasbni tanlang')),
    )
    worker = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Xodim",
        widget=_worker_select_widget('Xodimni tanlang'),
    )

    def __init__(self, *args, **kwargs):
        section_admin = kwargs.pop('section_admin', None)
        membership = kwargs.pop('membership', None)
        super().__init__(*args, **kwargs)
        section = get_section_admin_section(section_admin) if section_admin else None
        if section:
            self.fields['profession'].queryset = Profession.objects.filter(
                industry=section.department.leader.industry
            ).order_by('name')
            self.fields['worker'].queryset = get_section_member_worker_choices(section_admin, membership)
            self.fields['worker'].label_from_instance = lambda user: (
                f"{getattr(user.profile, 'full_name', '') or user.username} ({user.username})"
            )
        if membership and membership.profession_id:
            self.fields['profession'].initial = membership.profession_id

    def clean_worker(self):
        worker = self.cleaned_data['worker']
        allowed_roles = {UserProfile.ROLE_WORKER, UserProfile.ROLE_SECTION_ADMIN}
        if worker.profile.role not in allowed_roles:
            raise ValidationError("Faqat xodimni tanlashingiz mumkin.")
        return worker


def build_full_name(first_name, last_name, middle_name=''):
    parts = [
        (first_name or '').strip(),
        (last_name or '').strip(),
        (middle_name or '').strip(),
    ]
    return ' '.join(part for part in parts if part)


class ProfileEditForm(forms.Form):
    error_messages = {
        'password_mismatch': "Parollar bir xil bo'lishi kerak.",
    }

    first_name = forms.CharField(label='Ism', max_length=150, widget=forms.TextInput(attrs=_field_attrs('Ism')))
    last_name = forms.CharField(label='Familya', max_length=150, widget=forms.TextInput(attrs=_field_attrs('Familya')))
    middle_name = forms.CharField(label='Sharifi', max_length=255, required=False, widget=forms.TextInput(attrs=_field_attrs('Sharifi')))
    phone = forms.CharField(label='Telefon raqam', widget=forms.TextInput(attrs=phone_widget_attrs()))
    email = forms.EmailField(label='Elektron pochta', required=False, widget=forms.EmailInput(attrs=_field_attrs('Elektron pochta')))
    position = forms.CharField(label='Lavozim', required=False, max_length=255, widget=forms.TextInput(attrs=_field_attrs('Lavozim')))
    address = forms.CharField(label='Manzil', required=False, widget=forms.Textarea(attrs={**_field_attrs('Manzil'), 'rows': 2}))
    region = forms.ModelChoiceField(queryset=Region.objects.all(), label='Viloyat', required=False, widget=forms.Select(attrs=_field_attrs('Viloyat')))
    organization_name = forms.CharField(label='Tashkilot nomi', required=False, max_length=255, widget=forms.TextInput(attrs=_field_attrs('Tashkilot nomi')))
    industry = forms.ModelChoiceField(queryset=Industry.objects.all(), label='Soha', required=False, widget=forms.Select(attrs=_field_attrs('Soha')))
    profile_photo = forms.ImageField(
        label='Profil rasmi',
        required=False,
        widget=forms.FileInput(
            attrs={
                'class': 'sr-only',
                'accept': 'image/jpeg,image/png,image/webp',
                'id': 'profile-photo-input',
            }
        ),
    )
    remove_photo = forms.BooleanField(label='Rasmni olib tashlash', required=False)
    password1 = forms.CharField(
        label='Yangi parol',
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={**_field_attrs('Yangi parol'), 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Parolni tasdiqlang',
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={**_field_attrs('Parolni tasdiqlang'), 'autocomplete': 'new-password'}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        profile = getattr(user, 'profile', None)
        if profile:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['middle_name'].initial = profile.middle_name
            self.fields['phone'].initial = profile.phone_number or user.username
            self.fields['position'].initial = profile.position
            self.fields['address'].initial = profile.address
            self.fields['region'].initial = profile.region
            
            if profile.role == UserProfile.ROLE_ORG_LEADER:
                self.fields['organization_name'].initial = profile.organization_name
                self.fields['industry'].initial = profile.industry
            else:
                del self.fields['organization_name']
                del self.fields['industry']
        self.fields['password1'].help_text = "O'zgartirmasangiz bo'sh qoldiring."
        self.fields['password2'].help_text = ''

    def clean_phone(self):
        phone = normalize_uz_phone(self.cleaned_data['phone'])
        qs = User.objects.filter(username=phone).exclude(pk=self.user.pk)
        if qs.exists():
            raise ValidationError("Bu telefon raqam allaqachon ro'yxatdan o'tgan.")
        if UserProfile.objects.filter(phone_number=phone).exclude(user=self.user).exists():
            raise ValidationError("Bu telefon raqam allaqachon ro'yxatdan o'tgan.")
        return phone

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        if not photo:
            return photo
        if photo.size > 20 * 1024 * 1024:
            raise ValidationError('Rasm hajmi 20 MB dan oshmasligi kerak.')
        content_type = getattr(photo, 'content_type', '') or ''
        if content_type and not content_type.startswith('image/'):
            raise ValidationError('Faqat rasm faylini yuklang.')
        return photo

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1', '')
        password2 = cleaned.get('password2', '')
        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', self.error_messages['password_mismatch'])
            elif len(password1) < 6:
                self.add_error('password1', ValidationError("Parol kamida 6 ta belgidan iborat bo'lishi kerak."))
        return cleaned

    def save(self):
        profile = self.user.profile
        phone = self.cleaned_data['phone']
        first_name = self.cleaned_data['first_name'].strip()
        last_name = self.cleaned_data['last_name'].strip()
        middle_name = self.cleaned_data.get('middle_name', '').strip()

        self.user.first_name = first_name
        self.user.last_name = last_name
        self.user.username = phone
        self.user.email = self.cleaned_data.get('email', '')
        if self.cleaned_data.get('password1'):
            self.user.set_password(self.cleaned_data['password1'])
        self.user.save()

        profile.middle_name = middle_name
        profile.full_name = build_full_name(first_name, last_name, middle_name)
        profile.phone_number = phone
        profile.position = self.cleaned_data.get('position', '')
        profile.address = self.cleaned_data.get('address', '')
        if 'region' in self.cleaned_data:
            profile.region = self.cleaned_data.get('region')
        
        if profile.role == UserProfile.ROLE_ORG_LEADER:
            profile.organization_name = self.cleaned_data.get('organization_name', '')
            profile.industry = self.cleaned_data.get('industry')
        if self.cleaned_data.get('remove_photo') and profile.profile_photo:
            profile.profile_photo.delete(save=False)
            profile.profile_photo = None
        elif self.cleaned_data.get('profile_photo'):
            if profile.profile_photo:
                profile.profile_photo.delete(save=False)
            profile.profile_photo = self.cleaned_data['profile_photo']
        profile.save()
        return profile


def get_section_workers_for_internal_guidelines(section):
    """Bo'lim ichki yo'riqnomalari — faqat xodimlar (nazoratchi emas)."""
    if not section:
        return User.objects.none()
    return (
        User.objects.filter(
            section_memberships__section=section,
            profile__role=UserProfile.ROLE_WORKER,
            is_superuser=False,
        )
        .select_related('profile')
        .distinct()
        .order_by('profile__full_name', 'username')
    )


_DATE_WIDGET = forms.DateInput(
    format='%Y-%m-%d',
    attrs={
        'type': 'date',
        'class': 'form-control block w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20',
    },
)


class SectionInternalGuidelineForm(forms.ModelForm):
    class Meta:
        model = SectionInternalGuideline
        fields = ('name', 'pdf_file', 'start_time', 'registration_end_time', 'active_until')
        widgets = {
            'name': forms.TextInput(attrs=_field_attrs('Yo‘riqnoma nomi')),
            'pdf_file': forms.FileInput(
                attrs={
                    'class': 'block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-emerald-700 hover:file:bg-emerald-100',
                    'accept': '.pdf,.docx',
                }
            ),
            'start_time': _DATE_WIDGET,
            'registration_end_time': _DATE_WIDGET,
            'active_until': _DATE_WIDGET,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('start_time', 'registration_end_time', 'active_until'):
            self.fields[field_name].required = True

    def clean_pdf_file(self):
        pdf = self.cleaned_data.get('pdf_file')
        if not pdf:
            if self.instance.pk and self.instance.pdf_file:
                return self.instance.pdf_file
            raise ValidationError('PDF fayl yuklang.')
        if pdf.size > 20 * 1024 * 1024:
            raise ValidationError('Fayl hajmi 20 MB dan oshmasligi kerak.')
        ext = pdf.name.split('.')[-1].lower() if getattr(pdf, 'name', None) else ''
        if ext not in ['pdf', 'docx']:
            raise ValidationError('Faqat PDF va DOCX formatlari qabul qilinadi.')
        return pdf

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        reg_end = cleaned.get('registration_end_time')
        active_until = cleaned.get('active_until')
        if start and reg_end and reg_end <= start:
            raise ValidationError("Ro'yxatdan o'tish oxiri boshlanish vaqtidan keyin bo'lishi kerak.")
        if reg_end and active_until and active_until <= reg_end:
            raise ValidationError('Faollik tugashi ro\'yxatdan o\'tish oxiridan keyin bo\'lishi kerak.')
        return cleaned


class EntryGuidelineForm(forms.ModelForm):
    class Meta:
        model = EntryGuideline
        fields = ('name', 'pdf_file')
        widgets = {
            'name': forms.TextInput(attrs=_field_attrs('Yo‘riqnoma nomi')),
            'pdf_file': forms.FileInput(
                attrs={
                    'class': 'block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-emerald-700 hover:file:bg-emerald-100',
                    'accept': '.pdf,.docx',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_pdf_file(self):
        pdf = self.cleaned_data.get('pdf_file')
        if not pdf:
            if self.instance.pk and self.instance.pdf_file:
                return self.instance.pdf_file
            raise ValidationError("PDF fayl yuklang.")
        if pdf.size > 20 * 1024 * 1024:
            raise ValidationError('Fayl hajmi 20 MB dan oshmasligi kerak.')
        ext = pdf.name.split('.')[-1].lower() if getattr(pdf, 'name', None) else ''
        if ext not in ['pdf', 'docx']:
            raise ValidationError('Faqat PDF va DOCX formatlari qabul qilinadi.')
        return pdf

    def clean(self):
        cleaned = super().clean()
        return cleaned


class SectionWorkPracticeForm(forms.ModelForm):
    class Meta:
        model = SectionWorkPractice
        fields = ('name', 'start_time', 'end_time', 'notes')
        widgets = {
            'name': forms.TextInput(attrs=_field_attrs('Ish amaliyoti nomi')),
            'start_time': _DATE_WIDGET,
            'end_time': _DATE_WIDGET,
            'notes': forms.Textarea(
                attrs={
                    'class': 'form-control block w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20',
                    'rows': 3,
                    'placeholder': 'Izoh (ixtiyoriy)',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        end = cleaned.get('end_time')
        if start and end and end <= start:
            raise ValidationError('Tugash vaqti boshlanish vaqtidan keyin bo‘lishi kerak.')
        return cleaned
