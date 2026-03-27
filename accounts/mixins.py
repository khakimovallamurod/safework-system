from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect


class RoleContextMixin:
    """Adds role flags used by templates."""

    def get_role_context(self):
        user = self.request.user
        try:
            company = user.company_profile
        except ObjectDoesNotExist:
            company = None
        is_company_admin = company is not None and not user.is_superuser
        return {
            'is_super_admin': user.is_superuser,
            'is_company_admin': is_company_admin,
            'role_name': 'Super admin' if user.is_superuser else ('Kompaniya egasi' if is_company_admin else 'Foydalanuvchi'),
            'company_profile': company,
            'company_industry': company.industry if company else None,
        }


class AuthenticatedRequiredMixin(LoginRequiredMixin, RoleContextMixin):
    login_url = 'login'


class SuperuserActionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restricts mutating actions to super admin only."""

    login_url = 'login'

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu amal faqat super admin uchun.")
            return redirect('dashboard')
        return redirect('login')


class ProfessionAccessRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    """Allows only super admin or company admin users."""

    login_url = 'login'

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        try:
            return self.request.user.company_profile is not None
        except ObjectDoesNotExist:
            return False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu bo'lim siz uchun yopiq.")
            return redirect('dashboard')
        return redirect('login')
