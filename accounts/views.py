from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView

from accounts.forms import OrganizationLeaderSignUpForm, SafeWorkAuthenticationForm, WorkerSignUpForm, normalize_uz_phone
from accounts.mixins import AuthenticatedRequiredMixin, SuperuserActionRequiredMixin
from accounts.models import UserProfile
from industries.models import Industry
from professions.models import Profession

User = get_user_model()


class LandingPageView(TemplateView):
    template_name = 'landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        industries = Industry.objects.annotate(profession_count=Count('professions')).order_by('name')[:6]
        context.update(
            {
                'industries': industries,
                'total_industries': Industry.objects.count(),
                'total_professions': Profession.objects.count(),
                'total_leaders': UserProfile.objects.filter(role=UserProfile.ROLE_ORG_LEADER).count(),
                'total_workers': UserProfile.objects.filter(role=UserProfile.ROLE_WORKER).count(),
            }
        )
        return context


class AdminLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = False
    authentication_form = SafeWorkAuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.is_superuser:
            messages.success(self.request, "Xush kelibsiz!")
        else:
            profile = getattr(self.request.user, 'profile', None)
            if profile and profile.role == UserProfile.ROLE_ORG_LEADER:
                messages.success(self.request, "Xush kelibsiz! Siz tashkilot rahbari sifatida kirdingiz.")
            else:
                messages.success(self.request, "Xush kelibsiz! Siz ishchi sifatida kirdingiz.")
        return response

    def form_invalid(self, form):
        username = self.request.POST.get('username', '').strip()
        try:
            normalized_username = normalize_uz_phone(username)
        except Exception:
            normalized_username = username
        user = User.objects.filter(username=normalized_username).first()
        if user and not user.is_active:
            messages.error(self.request, "Akkauntingiz bloklangan. Tizimga kirish mumkin emas.")
        return super().form_invalid(form)


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy('home')


class RegisterChoiceView(TemplateView):
    template_name = 'accounts/register_choice.html'


class OrganizationLeaderRegisterView(FormView):
    template_name = 'accounts/register_leader.html'
    form_class = OrganizationLeaderSignUpForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Rahbar akkaunti yaratildi. Endi tizimga kirishingiz mumkin.")
        return super().form_valid(form)


class WorkerRegisterView(FormView):
    template_name = 'accounts/register_worker.html'
    form_class = WorkerSignUpForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Ishchi akkaunti yaratildi. Endi tizimga kirishingiz mumkin.")
        return super().form_valid(form)


class DashboardView(AuthenticatedRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role_context = self.get_role_context()
        context.update(role_context)

        if role_context['is_super_admin']:
            context['total_industries'] = Industry.objects.count()
            context['total_leaders'] = UserProfile.objects.filter(role=UserProfile.ROLE_ORG_LEADER).count()
            context['total_workers'] = UserProfile.objects.filter(role=UserProfile.ROLE_WORKER).count()
            context['new_leaders'] = UserProfile.objects.filter(
                role=UserProfile.ROLE_ORG_LEADER,
                is_new_registration=True,
            ).count()
        elif role_context['user_profile'] and role_context['user_profile'].industry:
            profile = role_context['user_profile']
            context['organization_name'] = profile.organization_name
            context['company_industry_name'] = profile.industry.name
            context['industry_profession_count'] = Profession.objects.filter(industry=profile.industry).count()
            if role_context['is_worker']:
                context['worker_colleagues_count'] = UserProfile.objects.filter(
                    role=UserProfile.ROLE_WORKER,
                    organization_name=profile.organization_name,
                ).count()
        return context


class UserManagementView(SuperuserActionRequiredMixin, TemplateView):
    template_name = 'accounts/users.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '').strip()
        organization_name = self.request.GET.get('organization', '').strip()

        leaders = User.objects.filter(
            is_superuser=False,
            profile__isnull=False,
            profile__role=UserProfile.ROLE_ORG_LEADER,
        ).select_related('profile')
        workers = User.objects.filter(
            is_superuser=False,
            profile__isnull=False,
            profile__role=UserProfile.ROLE_WORKER,
        ).select_related('profile')

        if q:
            lookup = (
                Q(username__icontains=q)
                | Q(profile__full_name__icontains=q)
                | Q(profile__organization_name__icontains=q)
            )
            leaders = leaders.filter(lookup)
            workers = workers.filter(lookup)

        organizations = list(
            UserProfile.objects.filter(
                role=UserProfile.ROLE_ORG_LEADER,
                organization_name__gt='',
            )
            .order_by('organization_name')
            .values_list('organization_name', flat=True)
            .distinct()
        )

        if organization_name:
            users = workers.filter(profile__organization_name=organization_name)
            page_title = f"{organization_name} ishchilari"
            page_description = "Tanlangan tashkilotga tegishli ishchilar ro'yxati."
            table_empty = "Bu tashkilot uchun ishchi topilmadi"
        else:
            users = leaders
            page_title = "Tashkilot rahbarlari"
            page_description = "Bu yerda faqat tashkilot rahbarlari ko'rsatiladi. Tashkilotni tanlasangiz, o'sha tashkilot ishchilari chiqadi."
            table_empty = "Tashkilot rahbari topilmadi"

        context.update(
            self.get_role_context()
            | {
                'managed_users': users.order_by('-profile__is_new_registration', '-date_joined'),
                'q': q,
                'organizations': organizations,
                'selected_organization': organization_name,
                'page_title': page_title,
                'page_description': page_description,
                'table_empty': table_empty,
                'showing_workers': bool(organization_name),
            }
        )
        return context


class ToggleUserBlockView(SuperuserActionRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        managed_user = User.objects.filter(pk=pk, is_superuser=False).select_related('profile').first()
        if not managed_user:
            messages.error(request, "Foydalanuvchi topilmadi.")
            return redirect('users')

        managed_user.is_active = not managed_user.is_active
        managed_user.save(update_fields=['is_active'])

        profile = getattr(managed_user, 'profile', None)
        if profile and profile.role == UserProfile.ROLE_ORG_LEADER and profile.is_new_registration:
            profile.is_new_registration = False
            profile.save(update_fields=['is_new_registration'])

        if managed_user.is_active:
            messages.success(request, "Foydalanuvchi qayta faollashtirildi.")
        else:
            messages.warning(request, "Foydalanuvchi bloklandi. Endi u tizimga kira olmaydi.")
        return redirect('users')
