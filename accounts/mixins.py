from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect


class RoleContextMixin:
    """Adds role flags used by templates."""

    def get_role_context(self):
        user = self.request.user
        try:
            profile = user.profile
        except ObjectDoesNotExist:
            profile = None
        is_org_leader = profile is not None and profile.role == 'organization_leader' and not user.is_superuser
        is_worker = profile is not None and profile.role == 'worker' and not user.is_superuser
        return {
            'is_super_admin': user.is_superuser,
            'is_org_leader': is_org_leader,
            'is_worker': is_worker,
            'is_company_admin': is_org_leader,
            'role_name': 'Boshqaruv' if user.is_superuser else ('Tashkilot rahbari' if is_org_leader else 'Ishchi'),
            'user_profile': profile,
            'company_profile': None,
            'company_industry': profile.industry if profile else None,
            'can_manage_professions': user.is_superuser or is_org_leader,
        }


class AuthenticatedRequiredMixin(LoginRequiredMixin, RoleContextMixin):
    login_url = 'login'


class SuperuserActionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    """Restricts mutating actions to internal management users only."""

    login_url = 'login'

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu amal siz uchun yopiq.")
            return redirect('dashboard')
        return redirect('login')


class ProfessionAccessRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    """Allows authenticated users with one of the configured roles."""

    login_url = 'login'

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        try:
            return self.request.user.profile is not None
        except ObjectDoesNotExist:
            return False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu bo'lim siz uchun yopiq.")
            return redirect('dashboard')
        return redirect('login')


class ProfessionManageRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    login_url = 'login'

    def test_func(self):
        role = self.get_role_context()
        return role['is_super_admin'] or role['is_org_leader']

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Kasb turlarini boshqarish huquqi sizda mavjud emas.")
            return redirect('professions:list')
        return redirect('login')
