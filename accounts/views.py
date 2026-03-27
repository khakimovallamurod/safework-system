from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from accounts.mixins import AuthenticatedRequiredMixin
from companies.models import Company
from industries.models import Industry
from professions.models import Profession

User = get_user_model()


class HomeRedirectView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return redirect('login')


class AdminLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.is_superuser:
            messages.success(self.request, "Xush kelibsiz! Siz super admin sifatida kirdingiz.")
        elif hasattr(self.request.user, 'company_profile'):
            messages.success(self.request, "Xush kelibsiz! Siz kompaniya egasi sifatida kirdingiz.")
        else:
            messages.success(self.request, "Xush kelibsiz! Siz foydalanuvchi sifatida kirdingiz.")
        return response

    def form_invalid(self, form):
        username = self.request.POST.get('username', '').strip()
        password = self.request.POST.get('password', '')
        company = Company.objects.filter(username=username, password=password).first()
        if company:
            if not company.user:
                company.user = User.objects.create_user(username=company.username, password=company.password)
                company.save(update_fields=['user'])
            login(self.request, company.user)
            messages.success(self.request, "Xush kelibsiz! Siz kompaniya egasi sifatida kirdingiz.")
            return redirect('dashboard')
        return super().form_invalid(form)


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy('login')


class DashboardView(AuthenticatedRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role_context = self.get_role_context()
        context.update(role_context)

        if role_context['is_super_admin']:
            context['total_industries'] = Industry.objects.count()
            context['total_companies'] = Company.objects.count()
        elif role_context['is_company_admin'] and role_context['company_profile']:
            company = role_context['company_profile']
            context['company_name'] = company.company_name
            context['company_industry_name'] = company.industry.name
            context['industry_profession_count'] = Profession.objects.filter(industry=company.industry).count()
        return context
