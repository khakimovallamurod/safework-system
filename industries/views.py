from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import SuperuserActionRequiredMixin
from industries.forms import IndustryCreateForm
from industries.models import Industry
from django.db.models import Prefetch
from accounts.models import UserProfile


class IndustryListView(SuperuserActionRequiredMixin, View):
    template_name = 'industries.html'

    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()
        sort = request.GET.get('sort', 'created_at')
        direction = request.GET.get('dir', 'desc')

        sort_map = {
            'id': 'id',
            'name': 'name',
            'created_at': 'created_at',
        }
        sort_field = sort_map.get(sort, 'created_at')
        if direction == 'desc':
            sort_field = f'-{sort_field}'

        industries = Industry.objects.prefetch_related(
            Prefetch('user_profiles', queryset=UserProfile.objects.filter(role=UserProfile.ROLE_ORG_LEADER), to_attr='organizations')
        ).all()
        if q:
            industries = industries.filter(name__icontains=q)
        industries = industries.order_by(sort_field)

        context = {
            'form': IndustryCreateForm(),
            'industries': industries,
            'q': q,
            'sort': sort,
            'dir': direction,
        }
        context.update({'is_super_admin': True, 'is_company_admin': False, 'role_name': 'Super admin'})
        return render(request, self.template_name, context)


class IndustryCreateView(SuperuserActionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = IndustryCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Soha muvaffaqiyatli qo'shildi.")
        else:
            messages.error(request, "Soha qo'shishda xatolik bor.")
        return redirect('industries:list')


class IndustryEditView(SuperuserActionRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        industry = get_object_or_404(Industry, pk=pk)
        form = IndustryCreateForm(request.POST, instance=industry)
        if form.is_valid():
            form.save()
            messages.success(request, "Soha tahrirlandi.")
            return redirect('industries:list')

        messages.error(request, "Tahrirlashda xatolik bor.")
        return redirect('industries:list')


class IndustryDeleteView(SuperuserActionRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        industry = get_object_or_404(Industry, pk=pk)
        industry.delete()
        messages.success(request, "Soha o'chirildi.")
        return redirect('industries:list')
