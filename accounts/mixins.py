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
        is_department_admin = profile is not None and profile.role == 'department_admin' and not user.is_superuser
        is_section_admin = profile is not None and profile.role == 'section_admin' and not user.is_superuser
        is_worker = profile is not None and profile.role == 'worker' and not user.is_superuser
        is_section_member = False
        if is_worker and user.is_authenticated:
            from companies.models import SectionMembership
            is_section_member = SectionMembership.objects.filter(user=user).exists()
        if user.is_superuser:
            role_name = 'Boshqaruv'
        elif is_org_leader:
            role_name = 'Tashkilot rahbari'
        elif is_department_admin:
            role_name = 'Boshqarma nazoratchisi'
        elif is_section_admin:
            role_name = 'Bo‘lim nazoratchisi'
        elif is_section_member:
            role_name = 'Xodim'
        else:
            role_name = 'Xodim'
        profile_photo_url = None
        profile_display_name = user.get_full_name() or user.username
        profile_short_name = (user.first_name or '').strip()
        if profile:
            profile_display_name = profile.full_name or profile_display_name
            if not profile_short_name and profile.full_name:
                profile_short_name = profile.full_name.split()[0]
            if profile.profile_photo:
                profile_photo_url = profile.profile_photo.url
        if not profile_short_name:
            profile_short_name = profile_display_name.split()[0] if profile_display_name else user.username
        return {
            'is_super_admin': user.is_superuser,
            'is_org_leader': is_org_leader,
            'is_department_admin': is_department_admin,
            'is_section_admin': is_section_admin,
            'is_section_member': is_section_member,
            'is_worker': is_worker,
            'is_company_admin': is_org_leader,
            'role_name': role_name,
            'user_profile': profile,
            'profile_photo_url': profile_photo_url,
            'profile_display_name': profile_display_name,
            'profile_short_name': profile_short_name,
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


class OrgLeaderRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    login_url = 'login'

    def test_func(self):
        return self.get_role_context().get('is_org_leader', False)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu sahifa faqat tashkilot rahbarlari uchun.")
            return redirect('dashboard')
        return redirect('login')


class DepartmentSupervisorOnlyMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    """Faqat boshqarma nazoratchisi (department_admin)."""

    login_url = 'login'

    def test_func(self):
        return self.get_role_context().get('is_department_admin', False)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu sahifa faqat boshqarma nazoratchilari uchun.")
            return redirect('dashboard')
        return redirect('login')


class DepartmentAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    login_url = 'login'

    def test_func(self):
        role = self.get_role_context()
        return role['is_super_admin'] or role.get('is_org_leader') or role.get('is_department_admin')

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu sahifa faqat boshqarma adminlari uchun.")
            return redirect('dashboard')
        return redirect('login')


class SectionAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    login_url = 'login'

    def test_func(self):
        return self.get_role_context().get('is_section_admin', False)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu sahifa faqat bo‘lim nazoratchilari uchun.")
            return redirect('dashboard')
        return redirect('login')


class SectionMemberRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    login_url = 'login'

    def test_func(self):
        return self.get_role_context().get('is_section_member', False)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu sahifa faqat bo‘lim xodimlari uchun.")
            return redirect('dashboard')
        return redirect('login')
