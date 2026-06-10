from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from accounts.mixins import ProfessionAccessRequiredMixin, ProfessionManageRequiredMixin
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
        if role['user_profile'] and role['user_profile'].industry and not role['is_super_admin']:
            professions = professions.filter(industry=role['user_profile'].industry)
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


class ProfessionCreateView(ProfessionManageRequiredMixin, View):
    def _resolve_industry(self, role, request):
        if role['is_org_leader'] and role['user_profile']:
            return role['user_profile'].industry

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


class ProfessionEditView(ProfessionManageRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        role = self.get_role_context()
        profession = get_object_or_404(Profession, pk=pk)

        if role['is_org_leader'] and role['user_profile'] and profession.industry_id != role['user_profile'].industry_id:
            messages.error(request, "Siz boshqa soha kasb turini tahrirlay olmaysiz.")
            return redirect('professions:list')

        form = ProfessionForm(request.POST, request.FILES, instance=profession)
        if form.is_valid():
            updated = form.save(commit=False)
            if role['is_org_leader'] and role['user_profile']:
                updated.industry = role['user_profile'].industry
            updated.save()
            messages.success(request, "Kasb turi tahrirlandi.")
        else:
            messages.error(request, "Kasb turi tahririda xatolik bor.")
        return redirect('professions:list')


class ProfessionPdfView(ProfessionAccessRequiredMixin, View):
    """Kasb nizomi PDF — alohida sahifa."""

    template_name = 'accounts/guideline_pdf_view.html'

    def get(self, request, pk, *args, **kwargs):
        profession = get_object_or_404(Profession, pk=pk)
        if not profession.nizom_file:
            messages.error(request, 'Nizom fayli topilmadi.')
            return redirect('professions:list')

        role = self.get_role_context()
        if role['user_profile'] and role['user_profile'].industry and not role['is_super_admin']:
            if profession.industry_id != role['user_profile'].industry_id:
                messages.error(request, 'Ruxsat yo‘q.')
                return redirect('professions:list')

        back_url = request.GET.get('next') or reverse('professions:list')
        if not url_has_allowed_host_and_scheme(
            back_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            back_url = reverse('professions:list')

        title = f'{profession.name} — Nizom'
        context = role | {
            'guideline': profession,
            'pdf_title': title,
            'pdf_url': profession.nizom_file.url,
            'back_url': back_url,
            'page_title': title,
            'receipt': None,
        }
        return render(request, self.template_name, context)


class ProfessionDeleteView(ProfessionManageRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        role = self.get_role_context()
        profession = get_object_or_404(Profession, pk=pk)

        if role['is_org_leader'] and role['user_profile'] and profession.industry_id != role['user_profile'].industry_id:
            messages.error(request, "Siz boshqa soha kasb turini o'chira olmaysiz.")
            return redirect('professions:list')

        profession.delete()
        messages.success(request, "Kasb turi o'chirildi.")
        return redirect('professions:list')
