from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from accounts.models import UserProfile
from accounts.views import SectionAdminManagementView, WorkerHierarchyView
from companies.models import Department, Section, SectionMembership


class WorkerHierarchyViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = get_user_model().objects.create_user(
            username='superadmin',
            password='secret123',
            is_superuser=True,
            is_staff=True,
        )
        self.org_leader_user = get_user_model().objects.create_user(
            username='leaderone',
            password='secret123',
        )
        self.org_leader_profile = UserProfile.objects.create(
            user=self.org_leader_user,
            role=UserProfile.ROLE_ORG_LEADER,
            full_name='Ali Valiev',
            organization_name='Acme Safety',
        )
        self.department = Department.objects.create(
            leader=self.org_leader_profile,
            name='Operatsiyalar',
        )
        self.section = Section.objects.create(
            department=self.department,
            name='Xavfsizlik',
        )
        self.worker_user = get_user_model().objects.create_user(
            username='workerone',
            password='secret123',
        )
        UserProfile.objects.create(
            user=self.worker_user,
            role=UserProfile.ROLE_WORKER,
            full_name='Bobur Karimov',
            organization_name='Acme Safety',
            department=self.department,
            section=self.section,
        )

    def _make_request(self, user):
        request = self.factory.get('/hierarchy/')
        request.user = user
        return request

    def test_super_admin_hierarchy_groups_include_organization_name(self):
        view = WorkerHierarchyView()
        view.setup(request=self._make_request(self.superuser))

        context = view.get_context_data()

        self.assertIn('hierarchy', context)
        self.assertTrue(context['hierarchy'])
        self.assertEqual(context['hierarchy'][0]['organization_name'], 'Acme Safety')
        self.assertEqual(context['hierarchy'][0]['departments'][0]['department'], self.department)

    def test_section_admin_view_builds_context_with_section_memberships(self):
        department_admin_user = get_user_model().objects.create_user(
            username='deptadmin',
            password='secret123',
        )
        department_admin_profile = UserProfile.objects.create(
            user=department_admin_user,
            role=UserProfile.ROLE_DEPARTMENT_ADMIN,
            full_name='Jasur Tursunov',
            organization_name='Acme Safety',
            department=self.department,
        )
        self.department.supervisor = department_admin_user
        self.department.save(update_fields=['supervisor'])
        SectionMembership.objects.create(section=self.section, user=self.worker_user)

        request = self.factory.get('/section-admins/')
        request.user = department_admin_user
        view = SectionAdminManagementView()
        view.setup(request=request)

        context = view.get_context_data()

        self.assertIn('sections', context)
        self.assertEqual(len(context['sections']), 1)
        self.assertEqual(context['sections'][0].worker_count, 1)
        self.assertEqual(len(context['sections'][0].membership_list), 1)
