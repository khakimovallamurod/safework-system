from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect

from accounts.role_navigation import get_worker_entry_guideline_context


class RoleContextMixin:
    """Adds role flags used by templates."""

    def _get_structure_context(self, profile, is_section_member):
        organization = getattr(profile, 'organization', None) if profile else None
        organization_name = ''
        department_name = ''
        section_name = ''

        if profile:
            organization_name = (
                getattr(organization, 'organization_name', '')
                or profile.organization_name
                or ''
            )
            if profile.department_id:
                department_name = profile.department.name
            if profile.section_id:
                section_name = profile.section.name

        if is_section_member:
            from companies.models import SectionMembership
            membership = (
                SectionMembership.objects.filter(user=self.request.user)
                .select_related('section', 'section__department', 'section__department__leader')
                .first()
            )
            if membership:
                section = membership.section
                department = section.department
                organization_name = department.leader.organization_name or organization_name
                department_name = department.name
                section_name = section.name

        return {
            'structure_organization_name': organization_name or '-',
            'structure_department_name': department_name or '-',
            'structure_section_name': section_name or '-',
        }

    def get_role_context(self):
        user = self.request.user
        try:
            profile = user.profile
        except ObjectDoesNotExist:
            profile = None
        is_super_admin = user.is_superuser or (profile is not None and profile.role == 'super_admin')
        is_org_leader = profile is not None and profile.role == 'organization_leader' and not is_super_admin
        is_department_admin = profile is not None and profile.role == 'department_admin' and not is_super_admin
        is_section_admin = profile is not None and profile.role == 'section_admin' and not is_super_admin
        is_worker = profile is not None and profile.role == 'worker' and not is_super_admin
        is_section_member = False
        can_view_work_practices = False
        if is_worker and user.is_authenticated:
            from companies.models import SectionMembership
            is_section_member = SectionMembership.objects.filter(user=user).exists()
        has_dept_assessment = False
        if user.is_authenticated:
            from companies.models import DepartmentAssessmentNotification
            has_dept_assessment = (
                is_department_admin
                or DepartmentAssessmentNotification.objects.filter(
                    user=user,
                    assessment__is_published=True,
                    assessment__is_active=True,
                ).exists()
            )
        if user.is_authenticated:
            from companies.models import SectionWorkPractice, SectionWorkPracticeAssignee
            can_view_work_practices = (
                is_super_admin
                or is_org_leader
                or is_department_admin
                or is_section_admin
                or is_section_member
                or SectionWorkPracticeAssignee.objects.filter(user=user).exists()
                or SectionWorkPractice.objects.filter(responsible_user=user).exists()
                or SectionWorkPractice.objects.filter(created_by=user).exists()
            )
        if is_super_admin:
            role_name = 'Super admin'
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
        context = {
            'is_super_admin': is_super_admin,
            'is_org_leader': is_org_leader,
            'is_department_admin': is_department_admin,
            'is_section_admin': is_section_admin,
            'is_section_member': is_section_member,
            'is_worker': is_worker,
            'is_company_admin': is_org_leader,
            'role_name': role_name,
            'can_view_work_practices': can_view_work_practices,
            'user_profile': profile,
            'profile_photo_url': profile_photo_url,
            'profile_display_name': profile_display_name,
            'profile_short_name': profile_short_name,
            'company_profile': None,
            'company_industry': profile.industry if profile else None,
            'can_manage_professions': is_super_admin or is_org_leader or is_department_admin,
            'has_dept_assessment': has_dept_assessment,
        }
        context.update(get_worker_entry_guideline_context(user, is_worker or is_section_admin))
        context.update(self._get_structure_context(profile, is_section_member))
        return context


class AuthenticatedRequiredMixin(LoginRequiredMixin, RoleContextMixin):
    login_url = 'login'


class SuperuserActionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    """Restricts mutating actions to internal management users only."""

    login_url = 'login'

    def test_func(self):
        role = self.get_role_context()
        return role.get('is_super_admin', False)

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
        return role['is_super_admin'] or role['is_org_leader'] or role.get('is_department_admin')

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


class WorkPracticeAccessRequiredMixin(LoginRequiredMixin, UserPassesTestMixin, RoleContextMixin):
    login_url = 'login'

    def test_func(self):
        return self.get_role_context().get('can_view_work_practices', False)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Ish amaliyotlari sahifasi siz uchun yopiq.")
            return redirect('dashboard')
        return redirect('login')
