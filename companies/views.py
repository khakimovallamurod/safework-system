from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import SuperuserActionRequiredMixin
from companies.forms import CompanyCreateForm
from companies.models import Company
from industries.models import Industry


class CompanyListView(SuperuserActionRequiredMixin, View):
    template_name = 'companies.html'

    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()
        sort = request.GET.get('sort', 'created_at')
        direction = request.GET.get('dir', 'desc')

        sort_map = {
            'id': 'id',
            'company_name': 'company_name',
            'industry': 'industry__name',
            'username': 'username',
            'created_at': 'created_at',
        }
        sort_field = sort_map.get(sort, 'created_at')
        if direction == 'desc':
            sort_field = f'-{sort_field}'

        companies = Company.objects.select_related('industry').all()
        if q:
            companies = companies.filter(company_name__icontains=q)
        companies = companies.order_by(sort_field)

        context = {
            'form': CompanyCreateForm(),
            'companies': companies,
            'industries': Industry.objects.all(),
            'q': q,
            'sort': sort,
            'dir': direction,
        }
        context.update({'is_super_admin': True, 'is_company_admin': False, 'role_name': 'Super admin'})
        return render(request, self.template_name, context)


class CompanyCreateView(SuperuserActionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = CompanyCreateForm(request.POST)
        if form.is_valid():
            company = form.save()
            messages.success(
                request,
                f"Kompaniya qo'shildi. Login: {company.username} | Parol: {company.password}",
            )
        else:
            messages.error(request, "Kompaniya qo'shishda xatolik bor.")
        return redirect('companies:list')


class CompanyEditView(SuperuserActionRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        company = get_object_or_404(Company, pk=pk)
        form = CompanyCreateForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, "Kompaniya tahrirlandi.")
            return redirect('companies:list')

        messages.error(request, "Tahrirlashda xatolik bor.")
        return redirect('companies:list')


class CompanyDeleteView(SuperuserActionRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        company = get_object_or_404(Company, pk=pk)
        company.delete()
        messages.success(request, "Kompaniya o'chirildi.")
        return redirect('companies:list')
