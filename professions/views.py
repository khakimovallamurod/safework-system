from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import ProfessionAccessRequiredMixin
from companies.models import Company
from industries.models import Industry
from professions.forms import ProfessionForm
from professions.models import Profession


class ProfessionListView(ProfessionAccessRequiredMixin, View):
    template_name = 'professions.html'

    def get(self, request, *args, **kwargs):
        role = self.get_role_context()
        q = request.GET.get('q', '').strip()
        company_id = request.GET.get('company_id', '').strip()
        sort = request.GET.get('sort', 'created_at')
        direction = request.GET.get('dir', 'desc')

        sort_map = {
            'id': 'id',
            'name': 'name',
            'industry': 'industry__name',
            'created_at': 'created_at',
        }
        sort_field = sort_map.get(sort, 'created_at')
        if direction == 'desc':
            sort_field = f'-{sort_field}'

        professions = Profession.objects.select_related('industry').prefetch_related('industry__companies').all()
        if role['is_company_admin'] and role['company_profile']:
            professions = professions.filter(industry=role['company_profile'].industry)
        elif role['is_super_admin'] and company_id.isdigit():
            company = Company.objects.filter(id=company_id).first()
            if company:
                professions = professions.filter(industry=company.industry)

        if q:
            professions = professions.filter(name__icontains=q)
        professions = professions.order_by(sort_field)

        form = ProfessionForm()

        context = {
            'form': form,
            'professions': professions,
            'q': q,
            'sort': sort,
            'dir': direction,
            'companies': Company.objects.select_related('industry').order_by('company_name') if role['is_super_admin'] else [],
            'selected_company_id': company_id,
        }
        context.update(role)
        return render(request, self.template_name, context)


class ProfessionCreateView(ProfessionAccessRequiredMixin, View):
    def _resolve_industry(self, role, request):
        if role['is_company_admin'] and role['company_profile']:
            return role['company_profile'].industry

        # Super admin fallback: use requested industry_id if sent,
        # otherwise first available industry.
        industry_id = request.POST.get('industry_id')
        if industry_id:
            return Industry.objects.filter(id=industry_id).first()
        return Industry.objects.order_by('id').first()

    def post(self, request, *args, **kwargs):
        role = self.get_role_context()
        form = ProfessionForm(request.POST, request.FILES)

        if form.is_valid():
            industry = self._resolve_industry(role, request)
            if not industry:
                messages.error(request, "Kasb turi yaratish uchun kamida bitta soha bo'lishi kerak.")
                return redirect('professions:list')

            profession = form.save(commit=False)
            profession.industry = industry
            profession.save()
            messages.success(request, "Kasb turi muvaffaqiyatli qo'shildi.")
        else:
            messages.error(request, "Kasb turi qo'shishda xatolik bor.")
        return redirect('professions:list')


class ProfessionEditView(ProfessionAccessRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        role = self.get_role_context()
        profession = get_object_or_404(Profession, pk=pk)

        if role['is_company_admin'] and role['company_profile'] and profession.industry_id != role['company_profile'].industry_id:
            messages.error(request, "Siz boshqa soha kasb turini tahrirlay olmaysiz.")
            return redirect('professions:list')

        form = ProfessionForm(request.POST, request.FILES, instance=profession)
        if form.is_valid():
            updated = form.save(commit=False)
            if role['is_company_admin'] and role['company_profile']:
                updated.industry = role['company_profile'].industry
            updated.save()
            messages.success(request, "Kasb turi tahrirlandi.")
        else:
            messages.error(request, "Kasb turi tahririda xatolik bor.")
        return redirect('professions:list')


class ProfessionDeleteView(ProfessionAccessRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        role = self.get_role_context()
        profession = get_object_or_404(Profession, pk=pk)

        if role['is_company_admin'] and role['company_profile'] and profession.industry_id != role['company_profile'].industry_id:
            messages.error(request, "Siz boshqa soha kasb turini o'chira olmaysiz.")
            return redirect('professions:list')

        profession.delete()
        messages.success(request, "Kasb turi o'chirildi.")
        return redirect('professions:list')
