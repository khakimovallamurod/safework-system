from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from django.utils.http import urlencode

from accounts.models import UserProfile, Region
from accounts.mixins import InspectionRequiredMixin, SuperAdminRequiredMixin
from inspection import services
from inspection.services import RegionScope


PAGE_SIZE = 25

TABLE_COLUMNS_WORKER = {
    'primary': 'Xodim / Korxona',
    'category': 'Kasb / Bo‘lim',
    'supervisor': 'Mas’ul nazoratchi / Telefon',
    'metric': 'Ko‘rsatkich',
}


class InspectionReadOnlyMixin(InspectionRequiredMixin):
    """Inspeksiya sahifalari faqat kuzatish uchun: har qanday POST/PUT/DELETE rad etiladi."""

    http_method_names = ['get', 'head', 'options']

    def get_scope(self):
        if not hasattr(self, '_scope'):
            self._scope = RegionScope(self.request.user, self.request.GET.get('region'))
        return self._scope

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scope = self.get_scope()
        region_query = f'region={scope.region.pk}' if scope.is_super_admin and scope.region else ''
        context.update({
            'scope': scope,
            'inspector_region': scope.region,
            'available_regions': scope.available_regions,
            'region_missing': scope.region_missing,
            'region_query': region_query,
            'show_staff_details': scope.show_staff_details,
        })
        return context


def _mandatory_label(type_key):
    return dict(services.MANDATORY_TYPES).get(type_key, '')


class InspectionRegistryView(InspectionReadOnlyMixin, TemplateView):
    """Yagona 7-ustunli read-only jadval sahifasi. Har bir bo'lim ``build_rows`` ni belgilaydi."""

    template_name = 'inspection/registry.html'
    page_key = ''
    title = ''
    subtitle = ''
    icon = 'bi-table'
    columns = TABLE_COLUMNS_WORKER
    status_filters = []
    org_filter = True
    empty_text = 'Ma’lumot topilmadi.'

    def build_rows(self, scope, profiles):
        raise NotImplementedError

    def get_tabs(self):
        return []

    def get_title(self):
        return self.title

    def get_kpis(self, rows):
        total = len(rows)
        kpis = [{'label': 'Jami yozuvlar', 'value': total, 'icon': 'bi-list-ol', 'tone': 'slate'}]
        for key, label, tone in self.status_filters:
            count = sum(1 for row in rows if row['status_key'] == key)
            kpis.append({
                'label': label, 'value': count, 'tone': tone,
                'hint': f'{services._pct(count, total)}%' if total else '',
            })
        return kpis[:5]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scope = self.get_scope()
        request = self.request

        selected_org = None
        org_param = request.GET.get('org', '').strip()
        if self.org_filter and org_param.isdigit():
            selected_org = scope.get_org_or_404(org_param)
        profiles = scope.profiles_for(selected_org.pk if selected_org else None)

        rows = self.build_rows(scope, profiles)
        kpis = self.get_kpis(rows)
        if not scope.show_staff_details:
            # Aggregate by organization so no person names, phones, per-person status, or searchable details leak.
            aggregate = {}
            for profile in profiles:
                org_id = scope.org_id_of(profile)
                if org_id:
                    item = aggregate.setdefault(org_id, {'total': 0, 'done': 0})
                    item['total'] += 1
            for row, profile in zip(rows, profiles):
                org_id = scope.org_id_of(profile)
                if org_id and row['status_key'] == 'done':
                    aggregate[org_id]['done'] += 1
            safe_rows = []
            for org in scope.orgs:
                counts = aggregate.get(org.pk)
                if not counts:
                    continue
                done = counts['done']
                pct = services._pct(done, counts['total'])
                safe_rows.append(services.make_row(
                    primary=org.organization_name or org.full_name,
                    category=org.industry.name if org.industry_id else '—',
                    metric=f'{done}/{counts["total"]}',
                    metric_sub=f'{pct}% bajarilgan', progress=pct,
                    status_key='done' if pct == 100 else ('pending' if done else 'missing'),
                    status_label=f'{pct}% bajarilgan', status_tone='emerald' if pct == 100 else ('amber' if done else 'rose'),
                    detail_url='',
                ))
            rows = safe_rows
            self.org_filter = False
        query = request.GET.get('q', '').strip() if scope.show_staff_details else ''
        status = request.GET.get('status', '').strip()
        if query:
            needle = query.lower()
            rows = [row for row in rows if needle in row['_search']]
        if status:
            rows = [row for row in rows if row['status_key'] == status]

        page_obj = Paginator(rows, PAGE_SIZE).get_page(request.GET.get('page'))
        params = request.GET.copy()
        params.pop('page', None)

        # Tab almashganda tanlangan korxona va viloyat saqlanib qoladi.
        tabs = self.get_tabs()
        keep = {key: request.GET[key] for key in ('org', 'region') if request.GET.get(key)}
        if keep:
            for tab in tabs:
                tab['url'] += ('&' if '?' in tab['url'] else '?') + urlencode(keep)

        context.update({
            'page_title': f'{self.get_title()} · Mehnat inspeksiyasi',
            'page_key': self.page_key,
            'heading': self.get_title(),
            'subtitle': self.subtitle,
            'icon': self.icon,
            'columns': self.columns,
            'kpis': kpis,
            'tabs': tabs,
            'status_filters': self.status_filters,
            'selected_status': status,
            'search_query': query,
            'org_filter': self.org_filter,
            'orgs': scope.orgs,
            'selected_org': selected_org,
            'page_obj': page_obj,
            'rows': page_obj.object_list,
            'row_offset': page_obj.start_index() - 1 if page_obj.paginator.count else 0,
            'filter_query': params.urlencode(),
            'empty_text': self.empty_text,
        })
        return context


# ─────────────────────────────────────────────────────────────
#  Boshqaruv paneli va korxonalar
# ─────────────────────────────────────────────────────────────

class InspectionDashboardView(InspectionReadOnlyMixin, TemplateView):
    """Hududiy umumiy monitoring: indekslar, qamrov va xavfsizlik reytingi."""

    template_name = 'inspection/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scope = self.get_scope()
        metrics = services.compute_org_metrics(scope)
        summary = services.region_summary(scope, metrics)
        ranked = services.build_company_rows(scope, metrics)
        risk_rows = [row for row in reversed(ranked) if row['status_key'] == 'risk'][:5]
        coverage = [
            {'label': 'Kirish yo‘riqnomasi', 'value': summary['entry_rate'], 'url': 'inspection:guidelines-entry'},
            {'label': 'Majburiy yo‘riqnomalar', 'value': summary['mandatory_rate'], 'url': 'inspection:guidelines-mandatory'},
            {'label': 'Stajirovka / mustaqil ruxsat', 'value': summary['practice_rate'], 'url': 'inspection:practices'},
            {'label': 'Tibbiy ko‘rik', 'value': summary['medical_rate'], 'url': 'inspection:medical'},
            {'label': 'IHV bilan ta’minlanganlik', 'value': summary['ppe_rate'], 'url': 'inspection:ppe'},
        ]
        context.update({
            'page_title': f"Mehnat inspeksiyasi · {scope.region.name if scope.region else 'Respublika'}",
            'summary': summary,
            'coverage': coverage,
            'ranked_rows': ranked[:10],
            'risk_rows': risk_rows,
            'columns': {
                'primary': 'Korxona / Rahbar',
                'category': 'Soha / Xodimlar',
                'supervisor': 'Mas’ul nazoratchi / Telefon',
                'metric': 'Xavfsizlik indeksi',
            },
        })
        return context


class InspectionCompanyRegistryView(InspectionRegistryView):
    page_key = 'companies'
    title = 'Korxonalar reestri'
    subtitle = 'Viloyatdagi barcha korxonalar, rahbarlari, mas’ul mutaxassislari va xodimlar soni.'
    icon = 'bi-buildings'
    org_filter = False
    columns = {
        'primary': 'Korxona / Rahbar',
        'category': 'Soha / Xodimlar',
        'supervisor': 'Mas’ul nazoratchi / Telefon',
        'metric': 'Xavfsizlik indeksi',
    }
    status_filters = [
        ('high', 'Yuqori xavfsizlik', 'emerald'),
        ('medium', 'O‘rta daraja', 'amber'),
        ('risk', 'Xavf ostida', 'rose'),
        ('nodata', "Ma'lumot yo'q", 'slate'),
    ]
    empty_text = 'Hududda ro‘yxatdan o‘tgan korxona topilmadi.'

    def build_rows(self, scope, profiles):
        return services.build_company_rows(scope, services.compute_org_metrics(scope))


class InspectionCompanyDetailView(InspectionReadOnlyMixin, TemplateView):
    """Tanlangan korxonani to'liq kuzatish (read-only)."""

    template_name = 'inspection/company_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scope = self.get_scope()
        if not scope.show_staff_details:
            from django.http import Http404
            raise Http404
        org = scope.get_org_or_404(kwargs['pk'])
        metrics = services.compute_org_metrics(scope)[org.pk]
        profiles = scope.profiles_for(org.pk)
        departments = [
            {
                'dept': dept,
                'supervisor': services._person_name(dept.supervisor),
                'supervisor_phone': services._person_phone(dept.supervisor),
                'sections': [s for s in scope.sections_by_id.values() if s.department_id == dept.pk],
            }
            for dept in scope.departments if dept.leader_id == org.pk
        ]
        coverage = [
            {'label': 'Kirish yo‘riqnomasi', 'value': metrics['entry_rate'], 'url': 'inspection:guidelines-entry'},
            {'label': 'Majburiy yo‘riqnomalar', 'value': metrics['mandatory_rate'], 'url': 'inspection:guidelines-mandatory'},
            {'label': 'Stajirovka / mustaqil ruxsat', 'value': metrics['practice_rate'], 'url': 'inspection:practices'},
            {'label': 'Tibbiy ko‘rik', 'value': metrics['medical_rate'], 'url': 'inspection:medical'},
            {'label': 'IHV bilan ta’minlanganlik', 'value': metrics['ppe_rate'], 'url': 'inspection:ppe'},
        ]
        context.update({
            'page_title': f"{metrics['organization_name']} · Mehnat inspeksiyasi",
            'org_profile': org,
            'metrics': metrics,
            'coverage': coverage,
            'departments': departments,
            'staff_rows': services.build_staff_rows(scope, profiles),
            'columns': TABLE_COLUMNS_WORKER | {'metric': 'Telefon / Mehnat holati'},
        })
        return context


class InspectionWorkerDetailView(InspectionReadOnlyMixin, TemplateView):
    """Xodimning mehnat muhofazasi bo'yicha to'liq varaqasi (read-only)."""

    template_name = 'inspection/worker_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scope = self.get_scope()
        if not scope.show_staff_details:
            from django.http import Http404
            raise Http404
        profile = scope.get_staff_or_404(kwargs['pk'])
        only = [profile]
        org_id = scope.org_id_of(profile)
        blocks = [
            ('Kirish yo‘riqnomasi', 'bi-file-earmark-check', services.build_entry_rows(scope, only)),
            ('Majburiy yo‘riqnomalar', 'bi-file-earmark-medical', services.build_mandatory_rows(scope, only)),
            ('Bo‘lim ichki yo‘riqnomasi', 'bi-journal-text', services.build_internal_rows(scope, only)),
            ('Kasbiy yo‘riqnoma', 'bi-person-lines-fill', services.build_profession_rows(scope, only)),
            ('Stajirovka jarayonlari', 'bi-briefcase', services.build_practice_rows(scope, only)),
            ('Test natijalari', 'bi-clipboard2-check', services.build_test_rows(scope, only)),
            ('Qoidabuzarliklar', 'bi-exclamation-octagon', services.build_violation_rows(scope, only)),
            ('Himoya vositalari (IHV)', 'bi-shield-shaded', services.build_ppe_rows(scope, only)),
            ('Tibbiy ko‘rik', 'bi-heart-pulse', services.build_medical_rows(scope, only)),
            ('Malaka sertifikatlari', 'bi-award', services.build_certificate_rows(scope, only)),
        ]
        person = scope.person_fields(profile)
        context.update({
            'page_title': f'{profile.full_name} · Mehnat inspeksiyasi',
            'worker': profile,
            'person': person,
            'org': scope.orgs_by_id.get(org_id),
            'blocks': [{'title': t, 'icon': i, 'rows': r} for t, i, r in blocks],
        })
        return context


# ─────────────────────────────────────────────────────────────
#  Yo'riqnomalar nazorati
# ─────────────────────────────────────────────────────────────

class InspectionEntryGuidelinesView(InspectionRegistryView):
    page_key = 'guidelines-entry'
    title = 'Kirish yo‘riqnomalari holati'
    subtitle = 'Har bir xodimning eng so‘nggi kirish yo‘riqnomasi bilan tanishganlik holati.'
    icon = 'bi-file-earmark-check'
    status_filters = [
        ('done', 'Tanishgan', 'emerald'),
        ('pending', 'Tanishmagan', 'rose'),
        ('missing', 'Yo‘riqnoma yo‘q', 'slate'),
    ]
    columns = TABLE_COLUMNS_WORKER | {'metric': 'Tanishgan sana / Yo‘riqnoma'}

    def build_rows(self, scope, profiles):
        return services.build_entry_rows(scope, profiles)


class InspectionMandatoryGuidelinesView(InspectionRegistryView):
    page_key = 'guidelines-mandatory'
    subtitle = 'Tibbiy, yong‘in va elektr xavfsizligi bo‘yicha amaldagi (eng so‘nggi faol) yo‘riqnomalar qamrovi.'
    icon = 'bi-file-earmark-medical'
    status_filters = [
        ('done', 'To‘liq tanishgan', 'emerald'),
        ('partial', 'Qisman', 'amber'),
        ('pending', 'Tanishmagan', 'rose'),
        ('missing', 'Yo‘riqnoma yo‘q', 'slate'),
    ]
    columns = TABLE_COLUMNS_WORKER | {'metric': 'Qamrov'}

    def get_type(self):
        value = self.request.GET.get('type', '')
        return value if value in dict(services.MANDATORY_TYPES) else ''

    def get_title(self):
        label = _mandatory_label(self.get_type())
        return f'Majburiy yo‘riqnomalar · {label}' if label else 'Majburiy yo‘riqnomalar'

    def get_tabs(self):
        base = reverse('inspection:guidelines-mandatory')
        current = self.get_type()
        tabs = [{'label': 'Barchasi', 'url': base, 'active': not current, 'param': ''}]
        for key, label in services.MANDATORY_TYPES:
            tabs.append({'label': label, 'url': f'{base}?type={key}', 'active': current == key, 'param': key})
        return tabs

    def build_rows(self, scope, profiles):
        return services.build_mandatory_rows(scope, profiles, self.get_type() or None)


class InspectionInternalGuidelinesView(InspectionRegistryView):
    page_key = 'guidelines-internal'
    title = 'Bo‘lim va ichki yo‘riqnomalar'
    subtitle = 'Bo‘limlar tomonidan yuborilgan ichki yo‘riqnomalar bilan tanishish holati.'
    icon = 'bi-journal-text'
    status_filters = [
        ('done', 'Tanishgan', 'emerald'),
        ('pending', 'Kutilmoqda', 'amber'),
        ('overdue', 'Muddatida tanishmagan', 'rose'),
        ('missing', 'Yuborilmagan', 'slate'),
    ]
    columns = TABLE_COLUMNS_WORKER | {'metric': 'Tanishgan sana / Yo‘riqnoma'}

    def build_rows(self, scope, profiles):
        return services.build_internal_rows(scope, profiles)


class InspectionProfessionGuidelinesView(InspectionRegistryView):
    page_key = 'guidelines-profession'
    title = 'Kasbiy yo‘riqnomalar qamrovi'
    subtitle = 'Xodimlarning o‘z kasbi bo‘yicha mehnat muhofazasi yo‘riqnomasi bilan tanishganligi.'
    icon = 'bi-person-lines-fill'
    status_filters = [
        ('done', 'Tanishgan', 'emerald'),
        ('pending', 'Tanishmagan', 'rose'),
        ('missing', 'Kasb yo‘riqnomasi yo‘q', 'slate'),
        ('noprof', 'Kasb biriktirilmagan', 'slate'),
    ]
    columns = TABLE_COLUMNS_WORKER | {'metric': 'Tanishgan sana / Kasb'}

    def build_rows(self, scope, profiles):
        return services.build_profession_rows(scope, profiles)


# ─────────────────────────────────────────────────────────────
#  Stajirovka va bilimni baholash
# ─────────────────────────────────────────────────────────────

class InspectionPracticesView(InspectionRegistryView):
    page_key = 'practices'
    title = 'Amaliyot / stajirovka jarayonlari'
    subtitle = 'Yangi xodimlarning stajirovka muddati, biriktirilgan ustozi va yakunlanish holati.'
    icon = 'bi-briefcase'
    status_filters = [
        ('active', 'Jarayonda', 'sky'),
        ('closed', 'Yakunlangan', 'emerald'),
        ('overdue', 'Muddati o‘tgan', 'rose'),
        ('upcoming', 'Boshlanmagan', 'slate'),
    ]
    columns = {
        'primary': 'Stajyor / Korxona',
        'category': 'Dastur / Bo‘lim',
        'supervisor': 'Mas’ul ustoz / Telefon',
        'metric': 'Muddat',
    }
    empty_text = 'Stajirovka jarayonlari topilmadi.'

    def build_rows(self, scope, profiles):
        return services.build_practice_rows(scope, profiles)


class InspectionTestResultsView(InspectionRegistryView):
    page_key = 'tests'
    title = 'Test natijalari va imtihon bayonnomalari'
    subtitle = 'Stajirovka yakuniy testlari va boshqarma bilimni baholash testlari natijalari.'
    icon = 'bi-clipboard2-check'
    status_filters = [
        ('passed', 'O‘tdi', 'emerald'),
        ('failed', 'O‘tmadi', 'rose'),
        ('progress', 'Yakunlanmagan', 'slate'),
    ]
    columns = {
        'primary': 'Xodim / Korxona',
        'category': 'Test / Turi',
        'supervisor': 'Mas’ul / Telefon',
        'metric': 'Ball / Sana',
    }
    empty_text = 'Test natijalari topilmadi.'

    def get_kind(self):
        value = self.request.GET.get('kind', '')
        return value if value in {'practice', 'assessment'} else ''

    def get_tabs(self):
        base = reverse('inspection:tests')
        kind = self.get_kind()
        return [
            {'label': 'Barchasi', 'url': base, 'active': not kind, 'param': ''},
            {'label': 'Stajirovka testlari', 'url': f'{base}?kind=practice', 'active': kind == 'practice', 'param': 'practice'},
            {'label': 'Bilimni baholash', 'url': f'{base}?kind=assessment', 'active': kind == 'assessment', 'param': 'assessment'},
        ]

    def build_rows(self, scope, profiles):
        return services.build_test_rows(scope, profiles, self.get_kind())


# ─────────────────────────────────────────────────────────────
#  Qoidabuzarliklar, IHV, sertifikatlar, tibbiy ko'rik
# ─────────────────────────────────────────────────────────────

class InspectionViolationsView(InspectionRegistryView):
    page_key = 'violations'
    title = 'Qoidabuzarliklar va holatlar'
    subtitle = 'Qayd etilgan qoidabuzarliklar, sabablari va ko‘rilgan choralar.'
    icon = 'bi-exclamation-octagon'
    status_filters = [
        ('active', 'Faol', 'rose'),
        ('resolved', 'Chora ko‘rilgan', 'emerald'),
    ]
    columns = {
        'primary': 'Xodim / Korxona',
        'category': 'Qoidabuzarlik turi / Sana',
        'supervisor': 'Qayd etgan nazoratchi / Telefon',
        'metric': 'Sabab / Chora',
    }
    empty_text = 'Qoidabuzarliklar qayd etilmagan.'

    def build_rows(self, scope, profiles):
        return services.build_violation_rows(scope, profiles)


class InspectionPPEView(InspectionRegistryView):
    page_key = 'ppe'
    title = 'Himoya vositalari (IHV) bilan ta’minlanganlik'
    subtitle = 'Xodimlarga berilgan individual himoya vositalari, qabul qilinishi va amal qilish muddati.'
    icon = 'bi-shield-shaded'
    status_filters = [
        ('ok', 'Ta’minlangan', 'emerald'),
        ('partial', 'Qisman', 'amber'),
        ('expired', 'Muddati o‘tgan', 'rose'),
        ('none', 'Berilmagan', 'rose'),
    ]
    columns = TABLE_COLUMNS_WORKER | {'metric': 'Amaldagi IHV'}

    def build_rows(self, scope, profiles):
        return services.build_ppe_rows(scope, profiles)


class InspectionCertificatesView(InspectionRegistryView):
    page_key = 'certificates'
    title = 'Xodimlar malaka sertifikatlari'
    subtitle = 'Xodimlar tomonidan olingan va tizimga yuklangan malaka sertifikatlari.'
    icon = 'bi-award'
    status_filters = []
    columns = {
        'primary': 'Xodim / Korxona',
        'category': 'Sertifikat turi / Bo‘lim',
        'supervisor': 'Mas’ul nazoratchi / Telefon',
        'metric': 'Yuklangan sana',
    }
    empty_text = 'Sertifikatlar yuklanmagan.'

    def build_rows(self, scope, profiles):
        return services.build_certificate_rows(scope, profiles)

    def get_kpis(self, rows):
        scope = self.get_scope()
        org_param = self.request.GET.get('org', '')
        profiles = scope.profiles_for(int(org_param) if org_param.isdigit() else None)
        covered = len({row['primary'] + row['primary_sub'] for row in rows})
        return [
            {'label': 'Jami sertifikatlar', 'value': len(rows), 'icon': 'bi-award', 'tone': 'slate'},
            {'label': 'Sertifikatga ega xodimlar', 'value': covered, 'tone': 'emerald',
             'hint': f'{services._pct(covered, len(profiles))}%' if profiles else ''},
            {'label': 'Jami xodimlar', 'value': len(profiles), 'tone': 'sky'},
        ]


class InspectionMedicalView(InspectionRegistryView):
    page_key = 'medical'
    title = 'Tibbiy ko‘rikdan o‘tganlik holati'
    subtitle = 'Har bir xodimning so‘nggi davriy tibbiy ko‘rigi va uning amal qilish muddati.'
    icon = 'bi-heart-pulse'
    status_filters = [
        ('ok', 'Amalda', 'emerald'),
        ('soon', 'Tugash arafasida', 'amber'),
        ('expired', 'Muddati o‘tgan', 'rose'),
        ('none', 'Ko‘rikdan o‘tmagan', 'rose'),
    ]
    columns = TABLE_COLUMNS_WORKER | {'metric': 'Amal qilish muddati'}

    def build_rows(self, scope, profiles):
        return services.build_medical_rows(scope, profiles)


# ==========================================
# SUPER ADMIN: INSPEKSIYA XODIMLARINI BOSHQARISH
# ==========================================

class InspectionAdminManageView(SuperAdminRequiredMixin, TemplateView):
    """Super admin uchun inspektsiya akkauntlarini yaratish va boshqarish."""
    template_name = 'inspection/admin_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        inspectors = UserProfile.objects.filter(
            role=UserProfile.ROLE_INSPECTION
        ).select_related('user', 'region').order_by('-user__date_joined')

        regions = Region.objects.all().order_by('name')

        context.update({
            'page_title': "Davlat mehnat inspeksiyasi nazoratchilari",
            'inspectors': inspectors,
            'regions': regions,
        })
        return context

    def post(self, request, *args, **kwargs):
        """Yangi inspektsiya xodimini qo'shish, tahrirlash yoki o'chirish."""
        from django.db import transaction, IntegrityError

        action = request.POST.get('action')

        if action == 'create':
            full_name = (request.POST.get('full_name') or '').strip()
            phone_number = (request.POST.get('phone_number') or '').strip()
            password = (request.POST.get('password') or '').strip()
            region_id = request.POST.get('region_id')

            if not phone_number or not password or not full_name or not region_id:
                messages.error(request, "Barcha majburiy maydonlarni (Ism, Viloyat, Telefon raqam, Parol) to‘ldiring!")
                return redirect('inspection:admin-manage')

            # Telefon raqamni tozalash va standart O'zbekiston formati (+998...) ga keltirish
            from accounts.forms import normalize_uz_phone
            try:
                clean_phone = normalize_uz_phone(phone_number)
            except Exception:
                digits = ''.join(ch for ch in phone_number if ch.isdigit())
                if len(digits) == 9:
                    clean_phone = f'+998{digits}'
                elif len(digits) == 12 and digits.startswith('998'):
                    clean_phone = f'+{digits}'
                else:
                    messages.error(request, "Telefon raqami noto‘g‘ri kiritildi. Masalan: 93 855 46 50")
                    return redirect('inspection:admin-manage')

            username = clean_phone

            existing_user = User.objects.filter(username=username).first()
            existing_p = UserProfile.objects.filter(phone_number=clean_phone).first()
            if existing_user or existing_p:
                conflict_name = existing_p.full_name if existing_p else existing_user.username
                messages.error(
                    request,
                    f"«{clean_phone}» telefon raqami bazada allaqachon mavjud ({conflict_name} akkauntiga biriktirilgan). Iltimos, boshqa telefon raqam kiriting."
                )
                return redirect('inspection:admin-manage')

            region = Region.objects.filter(id=region_id).first()
            if not region:
                messages.error(request, "Viloyat topilmadi.")
                return redirect('inspection:admin-manage')

            inspection_detail_access = request.POST.get('inspection_detail_access') == '1'

            try:
                with transaction.atomic():
                    user = User.objects.create_user(username=username, password=password)
                    UserProfile.objects.create(
                        user=user,
                        role=UserProfile.ROLE_INSPECTION,
                        full_name=full_name,
                        phone_number=clean_phone,
                        region=region,
                        position="Davlat mehnat inspektori",
                        inspection_detail_access=inspection_detail_access,
                    )
                messages.success(request, f"Inspektor «{full_name}» ({clean_phone}) muvaffaqiyatli qo‘shildi.")
            except IntegrityError:
                messages.error(request, f"Ushbu telefon raqam bilan akkaunt allaqachon mavjud.")
            except Exception as e:
                messages.error(request, f"Xatolik: {str(e)}")

        elif action == 'edit':
            inspector_id = request.POST.get('inspector_id')
            profile = get_object_or_404(UserProfile, id=inspector_id, role=UserProfile.ROLE_INSPECTION)

            full_name = (request.POST.get('full_name') or '').strip()
            phone_number = (request.POST.get('phone_number') or '').strip()
            region_id = request.POST.get('region_id')
            new_password = (request.POST.get('new_password') or '').strip()

            clean_phone = None
            if phone_number:
                from accounts.forms import normalize_uz_phone
                try:
                    clean_phone = normalize_uz_phone(phone_number)
                except Exception:
                    digits = ''.join(ch for ch in phone_number if ch.isdigit())
                    if len(digits) == 9:
                        clean_phone = f'+998{digits}'
                    elif len(digits) == 12 and digits.startswith('998'):
                        clean_phone = f'+{digits}'
                    else:
                        messages.error(request, "Telefon raqami noto‘g‘ri kiritildi.")
                        return redirect('inspection:admin-manage')

                existing_u = User.objects.filter(username=clean_phone).exclude(id=profile.user.id).first()
                existing_p = UserProfile.objects.filter(phone_number=clean_phone).exclude(id=profile.id).first()
                if existing_u or existing_p:
                    conflict_name = existing_p.full_name if existing_p else existing_u.username
                    messages.error(
                        request,
                        f"«{clean_phone}» telefon raqami allaqachon boshqa foydalanuvchiga ({conflict_name}) biriktirilgan."
                    )
                    return redirect('inspection:admin-manage')

            try:
                with transaction.atomic():
                    if full_name:
                        profile.full_name = full_name
                    if clean_phone:
                        profile.phone_number = clean_phone
                        profile.user.username = clean_phone
                        profile.user.save()
                    if region_id and region_id.isdigit():
                        profile.region_id = int(region_id)
                    if 'inspection_detail_access' in request.POST:
                        profile.inspection_detail_access = request.POST.get('inspection_detail_access') == '1'
                    profile.save()

                    if new_password:
                        profile.user.set_password(new_password)
                        profile.user.save()

                messages.success(request, f"Inspektor «{profile.full_name}» ma’lumotlari yangilandi.")
            except IntegrityError:
                messages.error(request, "Ma'lumotlarni saqlashda xatolik: telefon raqam takrorlangan bo'lishi mumkin.")
            except Exception as e:
                messages.error(request, f"Xatolik: {str(e)}")

        elif action == 'toggle-detail-access':
            inspector_id = request.POST.get('inspector_id')
            profile = get_object_or_404(UserProfile, id=inspector_id, role=UserProfile.ROLE_INSPECTION)
            profile.inspection_detail_access = not profile.inspection_detail_access
            profile.save(update_fields=['inspection_detail_access'])
            state = 'kengaytirilgan (xodim tafsilotlari ochiq)' if profile.inspection_detail_access else 'umumiy (faqat son va foizlar)'
            messages.success(request, f'{profile.full_name} uchun inspeksiya ko‘rish ruxsati {state} holatiga o‘zgartirildi.')

        elif action == 'delete':
            inspector_id = request.POST.get('inspector_id')
            profile = get_object_or_404(UserProfile, id=inspector_id, role=UserProfile.ROLE_INSPECTION)
            user = profile.user
            name = profile.full_name
            user.delete()
            messages.success(request, f"Inspektor «{name}» tizimdan o‘chirildi.")

        return redirect('inspection:admin-manage')


class InspectionToggleStatusView(SuperAdminRequiredMixin, View):
    """Bildirishnomadagi kabi ON/OFF iconka bilan inspektorni bloklash yoki faollashtirish (AJAX)."""

    def post(self, request, pk, *args, **kwargs):
        profile = get_object_or_404(UserProfile, pk=pk, role=UserProfile.ROLE_INSPECTION)
        user = profile.user
        # Toggle is_active
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])

        return JsonResponse({
            'success': True,
            'is_active': user.is_active,
            'inspector_id': profile.id,
            'message': f"Inspektor holati: {'Faol (Yoqilgan)' if user.is_active else 'Bloklangan (O‘chirilgan)'}"
        })
