import logging
from django import forms
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView

from accounts.models import UserProfile, Region
from accounts.notifications import send_action_notification
from .oneid import OneIDService

logger = logging.getLogger(__name__)
User = get_user_model()


class OneIdLoginView(View):
    """
    Foydalanuvchini id.egov.uz One ID tizimiga yo'naltirish.
    """
    def get(self, request, *args, **kwargs):
        service = OneIDService()
        if not service.client_id:
            messages.error(
                request,
                "One ID tizimi hali to‘liq sozlanmagan. Tizim ma'muri ONEID_CLIENT_ID va ONEID_CLIENT_SECRET kalitlarini kiritishi zarur."
            )
            return redirect('login')

        auth_url = service.get_authorization_url(request)
        return redirect(auth_url)


class OneIdCallbackView(View):
    """
    One ID tizimidan qaytgan foydalanuvchini qabul qilish va identifikatsiya qilish.
    """
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code')
        error = request.GET.get('error')

        if error:
            messages.error(request, f"One ID orqali kirish bekor qilindi yoki xatolik: {error}")
            return redirect('login')

        if not code:
            messages.error(request, "One ID tizimidan avtorizatsiya kodi olinmadi.")
            return redirect('login')

        service = OneIDService()
        user_info = service.exchange_code_for_user_info(code, request)

        if not user_info or 'error' in user_info:
            err_msg = user_info.get('error', 'One ID dan ma\'lumotlarni olishda xatolik yuz berdi.') if user_info else 'Noma\'lum xatolik.'
            messages.error(request, err_msg)
            return redirect('login')

        pinfl = user_info.get('pinfl')

        # 1. Tizimda mavjud foydalanuvchini PINFL yoki Passport orqali tekshirish
        existing_profile = None
        if pinfl:
            existing_profile = UserProfile.objects.filter(pinfl=pinfl).select_related('user').first()

        if not existing_profile and user_info.get('passport_series') and user_info.get('passport_number'):
            existing_profile = UserProfile.objects.filter(
                passport_series__iexact=user_info['passport_series'],
                passport_number=user_info['passport_number']
            ).select_related('user').first()

        if existing_profile:
            # Mavjud foydalanuvchi ma'lumotlarini yangilash va tizimga kiritish
            user = existing_profile.user
            if not existing_profile.pinfl and pinfl:
                existing_profile.pinfl = pinfl
                existing_profile.save(update_fields=['pinfl'])

            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            messages.success(request, f"Xush kelibsiz, {existing_profile.full_name or user.username}!")
            return redirect('dashboard')

        # 2. Agar foydalanuvchi yangi bo'lsa -> Sessiyaga saqlab, korxonani tanlashga yo'naltirish
        request.session['oneid_pending_user'] = user_info
        return redirect('oneid-complete')


class OneIdCompleteRegistrationForm(forms.Form):
    organization = forms.ModelChoiceField(
        label="Tashkilotni (Korxona / Zavod) tanlang",
        queryset=UserProfile.objects.filter(role=UserProfile.ROLE_ORG_LEADER).select_related('industry').order_by('organization_name', 'full_name'),
        empty_label="Tashkilotni tanlang",
        widget=forms.Select(attrs={
            'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10',
        })
    )
    region = forms.ModelChoiceField(
        label="Viloyatni tanlang",
        queryset=Region.objects.order_by('name'),
        required=False,
        empty_label="Viloyatni tanlang",
        widget=forms.Select(attrs={
            'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10',
        })
    )


class OneIdCompleteRegistrationView(FormView):
    """
    One ID orqali kirgan yangi xodimning korxona (zavod) biriktirmasini yakunlash.
    """
    template_name = 'accounts/oneid_complete.html'
    form_class = OneIdCompleteRegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if 'oneid_pending_user' not in request.session:
            messages.warning(request, "Avval One ID orqali tizimga kiring.")
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['oneid_user'] = self.request.session.get('oneid_pending_user', {})
        return context

    def form_valid(self, form):
        user_info = self.request.session.pop('oneid_pending_user', None)
        if not user_info:
            messages.error(self.request, "Sessiya muddati tugagan. Iltimos, qaytadan One ID orqali kiring.")
            return redirect('login')

        organization = form.cleaned_data['organization']
        region = form.cleaned_data.get('region') or organization.region

        # Username generatsiya: telefon raqami yoki PINFL
        pinfl = user_info.get('pinfl', '')
        phone = user_info.get('phone_number', '')
        base_username = pinfl if pinfl else (phone if phone else f"user_{pinfl}")
        username = base_username

        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        import secrets
        random_pwd = secrets.token_urlsafe(16)
        user = User.objects.create_user(
            username=username,
            password=random_pwd,
            first_name=user_info.get('first_name', ''),
            last_name=user_info.get('last_name', ''),
            email=user_info.get('email', ''),
        )

        profile = UserProfile.objects.create(
            user=user,
            role=UserProfile.ROLE_WORKER,
            full_name=user_info.get('full_name') or f"{user.first_name} {user.last_name}".strip(),
            middle_name=user_info.get('middle_name', ''),
            phone_number=phone or username,
            pinfl=pinfl,
            passport_series=user_info.get('passport_series', ''),
            passport_number=user_info.get('passport_number', ''),
            one_id_user_id=user_info.get('one_id_user_id', ''),
            birth_date=user_info.get('birth_date'),
            organization=organization,
            organization_name=organization.organization_name,
            industry=organization.industry,
            region=region,
            is_new_registration=True,
            is_approved_by_dept=False,  # 9-band: Boshqarma boshlig'i qabul qilishi kutiladi
        )

        # Boshqarma boshlig'i va direktorga yangi ro'yxatdan o'tgan xodim haqida bildirishnoma yuborish
        try:
            from companies.models import Department
            departments = Department.objects.filter(leader=organization).select_related('supervisor')
            dept_supervisors = [d.supervisor for d in departments if d.supervisor]
            if organization.user:
                dept_supervisors.append(organization.user)

            if dept_supervisors:
                send_action_notification(
                    title="Yangi xodim ro‘yxatdan o‘tdi (One ID)",
                    message=f"{profile.full_name} One ID orqali ro‘yxatdan o‘tdi. Iltimos, xodimni qabul qiling.",
                    notif_type='system',
                    url='/boshqarma-xodimlari/',
                    target_users=dept_supervisors,
                    exclude_users=[user]
                )
        except Exception:
            logger.exception("Failed to send new worker registration notification")

        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(self.request, user)
        messages.success(
            self.request,
            f"Muvaffaqiyatli ro‘yxatdan o‘tdingiz! Siz «{organization.organization_name}» korxonasiga biriktirildingiz."
        )
        return redirect('dashboard')
