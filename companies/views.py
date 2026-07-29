from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import SuperuserActionRequiredMixin
from django.db.models import Count
from companies.models import Department

class CompanyListView(SuperuserActionRequiredMixin, View):
    template_name = 'companies.html'

    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()
        sort = request.GET.get('sort', 'created_at')
        direction = request.GET.get('dir', 'desc')

        sort_map = {
            'id': 'id',
            'name': 'name',
            'leader': 'leader__organization_name',
            'created_at': 'created_at',
        }
        sort_field = sort_map.get(sort, 'created_at')
        if direction == 'desc':
            sort_field = f'-{sort_field}'

        departments = Department.objects.select_related('leader', 'supervisor').annotate(
            sections_count=Count('sections', distinct=True),
            workers_count=Count('team_members', distinct=True)
        )
        
        if q:
            departments = departments.filter(name__icontains=q)
        departments = departments.order_by(sort_field)

        context = {
            'departments': departments,
            'q': q,
            'sort': sort,
            'dir': direction,
        }
        context.update({'is_super_admin': True, 'is_company_admin': False, 'role_name': 'Super admin'})
        return render(request, self.template_name, context)
