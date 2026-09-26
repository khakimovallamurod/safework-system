"""Mehnat inspeksiyasi (read-only) uchun hududiy ma'lumotlarni yig'ish.

Barcha hisob-kitoblar bitta ``RegionScope`` orqali olib boriladi: u inspektorning
viloyatidagi korxonalar, boshqarmalar, bo'limlar va xodimlarni belgilangan
miqdordagi SQL so'rovlar bilan yuklaydi (korxona/xodim soniga bog'liq N+1 yo'q).
Har bir ``build_*_rows`` funksiyasi yagona 7-ustunli jadval qatorlarini qaytaradi.
"""
import datetime
from collections import defaultdict
from functools import cached_property

from django.db.models import Q
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from accounts.models import Region, UserProfile
from companies.models import (
    Department,
    DepartmentAssessmentAttempt,
    EmployeeCertificate,
    EmployeeMedicalRecord,
    GuidelineDispatch,
    GuidelineDispatchRecipient,
    MandatoryGuideline,
    MandatoryGuidelineReceipt,
    ProfessionGuidelineReceipt,
    Section,
    SectionInternalGuidelineRecipient,
    SectionMembership,
    SectionWorkPracticeAssignee,
    WorkPracticeTestAttempt,
)
from ppe.models import PPEIssue
from violations.models import Violation


STAFF_ROLES = (
    UserProfile.ROLE_WORKER,
    UserProfile.ROLE_SECTION_ADMIN,
    UserProfile.ROLE_DEPARTMENT_ADMIN,
)

MANDATORY_TYPES = [
    (MandatoryGuideline.TYPE_MEDICAL, 'Tibbiy yordam'),
    (MandatoryGuideline.TYPE_FIRE, "Yong'in xavfsizligi"),
    (MandatoryGuideline.TYPE_ELECTRIC, 'Elektr xavfsizligi'),
]

DEFAULT_PRACTICE_PASS_PERCENT = 70
ASSESSMENT_PASS_PERCENT = 60

TONE_BADGES = {
    'emerald': 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    'amber': 'bg-amber-50 text-amber-700 ring-amber-600/20',
    'rose': 'bg-rose-50 text-rose-700 ring-rose-600/20',
    'sky': 'bg-sky-50 text-sky-700 ring-sky-600/20',
    'slate': 'bg-slate-100 text-slate-600 ring-slate-500/20',
}

DASH = '—'


def _pct(part, total):
    return round(part * 100 / total) if total else 0


def _fmt_date(value):
    if not value:
        return DASH
    if hasattr(value, 'hour'):
        value = timezone.localtime(value)
    return value.strftime('%d.%m.%Y')


def _person_name(user):
    if not user:
        return ''
    profile = getattr(user, 'profile', None)
    return (profile.full_name if profile and profile.full_name else '') or user.get_full_name() or user.username


def _person_phone(user):
    if not user:
        return ''
    profile = getattr(user, 'profile', None)
    return (profile.phone_number if profile and profile.phone_number else '') or user.username


def make_row(*, primary, primary_sub='', category='', category_sub='', supervisor='', supervisor_phone='',
             metric='', metric_sub='', progress=None, status_key='', status_label='', status_tone='slate',
             detail_url='', detail_external=False, search_extra=''):
    """Barcha inspeksiya jadvallari uchun yagona qator formati."""
    return {
        'primary': primary or DASH,
        'primary_sub': primary_sub,
        'category': category or DASH,
        'category_sub': category_sub,
        'supervisor': supervisor or 'Tayinlanmagan',
        'supervisor_phone': supervisor_phone,
        'metric': metric if metric not in (None, '') else DASH,
        'metric_sub': metric_sub,
        'progress': progress,
        'status_key': status_key,
        'status_label': status_label,
        'status_tone': status_tone,
        'badge_class': TONE_BADGES.get(status_tone, TONE_BADGES['slate']),
        'detail_url': detail_url,
        'detail_external': detail_external,
        '_search': ' '.join(
            str(part) for part in (primary, primary_sub, category, category_sub, supervisor, search_extra) if part
        ).lower(),
    }


def safety_status(index, has_workers=True):
    if not has_workers:
        return 'nodata', "Ma'lumot yo'q", 'slate'
    if index >= 85:
        return 'high', 'Yuqori xavfsizlik', 'emerald'
    if index >= 60:
        return 'medium', 'O‘rta daraja', 'amber'
    return 'risk', 'Xavf ostida', 'rose'


class RegionScope:
    """Inspektorga ko'rinadigan hudud va undagi barcha tuzilmalar."""

    def __init__(self, user, requested_region_id=None):
        self.user = user
        profile = getattr(user, 'profile', None)
        self.is_super_admin = user.is_superuser or (profile is not None and profile.role == UserProfile.ROLE_SUPER_ADMIN)
        self.show_staff_details = bool(
            self.is_super_admin or (profile and profile.role == UserProfile.ROLE_INSPECTION and profile.inspection_detail_access)
        )
        self.region_missing = False

        if self.is_super_admin:
            self.available_regions = Region.objects.order_by('name')
            region = None
            if requested_region_id and str(requested_region_id).isdigit():
                region = Region.objects.filter(pk=int(requested_region_id)).first()
            self.region = region
        else:
            self.region = profile.region if profile and profile.region_id else None
            self.available_regions = Region.objects.filter(pk=self.region.pk) if self.region else Region.objects.none()
            # Viloyat biriktirilmagan inspektor hech narsa ko'rmaydi (region isolation).
            self.region_missing = self.region is None

        self.now = timezone.now()
        self.today = timezone.localdate()

    # ── Tuzilma ──────────────────────────────────────────────
    @cached_property
    def orgs(self):
        if self.region_missing:
            return []
        qs = UserProfile.objects.filter(role=UserProfile.ROLE_ORG_LEADER).select_related('user', 'industry', 'region')
        if self.region:
            qs = qs.filter(region=self.region)
        return list(qs.order_by('organization_name', 'full_name'))

    @cached_property
    def orgs_by_id(self):
        return {org.pk: org for org in self.orgs}

    @cached_property
    def departments(self):
        if not self.orgs:
            return []
        return list(
            Department.objects.filter(leader_id__in=self.orgs_by_id.keys())
            .select_related('supervisor__profile')
            .order_by('name')
        )

    @cached_property
    def departments_by_id(self):
        return {dept.pk: dept for dept in self.departments}

    @cached_property
    def sections_by_id(self):
        if not self.departments:
            return {}
        return {
            sec.pk: sec
            for sec in Section.objects.filter(department_id__in=self.departments_by_id.keys())
            .select_related('supervisor__profile', 'department')
        }

    @cached_property
    def staff(self):
        org_ids = list(self.orgs_by_id.keys())
        if not org_ids:
            return []
        dept_ids = list(self.departments_by_id.keys())
        sec_ids = list(self.sections_by_id.keys())
        return list(
            UserProfile.objects.filter(role__in=STAFF_ROLES)
            .filter(
                Q(organization_id__in=org_ids)
                | Q(department_id__in=dept_ids)
                | Q(section_id__in=sec_ids)
                | Q(user__section_memberships__section_id__in=sec_ids)
            )
            .select_related('user', 'department', 'section')
            .distinct()
            .order_by('full_name')
        )

    @cached_property
    def staff_by_user(self):
        return {p.user_id: p for p in self.staff}

    @cached_property
    def memberships_by_user(self):
        if not self.staff:
            return {}
        return {
            m.user_id: m
            for m in SectionMembership.objects.filter(user_id__in=self.staff_by_user.keys())
            .select_related('profession', 'section')
        }

    def section_of(self, profile):
        if profile.section_id and profile.section_id in self.sections_by_id:
            return self.sections_by_id[profile.section_id]
        membership = self.memberships_by_user.get(profile.user_id)
        if membership and membership.section_id in self.sections_by_id:
            return self.sections_by_id[membership.section_id]
        return None

    def department_of(self, profile):
        if profile.department_id and profile.department_id in self.departments_by_id:
            return self.departments_by_id[profile.department_id]
        section = self.section_of(profile)
        return self.departments_by_id.get(section.department_id) if section else None

    def org_id_of(self, profile):
        if profile.organization_id in self.orgs_by_id:
            return profile.organization_id
        department = self.department_of(profile)
        return department.leader_id if department else None

    @cached_property
    def staff_by_org(self):
        grouped = defaultdict(list)
        for profile in self.staff:
            org_id = self.org_id_of(profile)
            if org_id:
                grouped[org_id].append(profile)
        return grouped

    def profession_of(self, profile):
        membership = self.memberships_by_user.get(profile.user_id)
        if membership and membership.profession_id:
            return membership.profession.name
        return profile.position or 'Kasb ko‘rsatilmagan'

    def supervisor_of(self, profile):
        """Xodimning mas'ul nazoratchisi: bo'lim → boshqarma nazoratchisi."""
        section = self.section_of(profile)
        if section and section.supervisor_id and section.supervisor_id != profile.user_id:
            return section.supervisor
        department = self.department_of(profile)
        if department and department.supervisor_id and department.supervisor_id != profile.user_id:
            return department.supervisor
        return None

    def org_supervisor(self, org):
        for dept in self.departments:
            if dept.leader_id == org.pk and dept.supervisor_id:
                return dept.supervisor
        return None

    def org_name(self, org_id):
        org = self.orgs_by_id.get(org_id)
        if not org:
            return ''
        return org.organization_name or org.full_name

    # ── Kirish nazorati ──────────────────────────────────────
    def get_org_or_404(self, pk):
        org = self.orgs_by_id.get(int(pk))
        if not org:
            raise Http404('Korxona topilmadi yoki sizning hududingizga tegishli emas.')
        return org

    def get_staff_or_404(self, pk):
        for profile in self.staff:
            if profile.pk == int(pk):
                return profile
        raise Http404('Xodim topilmadi yoki sizning hududingizga tegishli emas.')

    def profiles_for(self, org_id=None, user_ids=None):
        profiles = self.staff_by_org.get(org_id, []) if org_id else [p for p in self.staff if self.org_id_of(p)]
        if user_ids is not None:
            profiles = [p for p in profiles if p.user_id in user_ids]
        return profiles

    # ── Umumiy qator maydonlari ──────────────────────────────
    def person_fields(self, profile):
        org_id = self.org_id_of(profile)
        section = self.section_of(profile)
        supervisor = self.supervisor_of(profile)
        return {
            'primary': profile.full_name or profile.user.username,
            'primary_sub': self.org_name(org_id),
            'category': self.profession_of(profile),
            'category_sub': section.name if section else (profile.department.name if profile.department_id else ''),
            'supervisor': _person_name(supervisor),
            'supervisor_phone': _person_phone(supervisor),
            'detail_url': reverse('inspection:worker-detail', args=[profile.pk]),
        }


# ─────────────────────────────────────────────────────────────
#  Korxona ko'rsatkichlari (bulk)
# ─────────────────────────────────────────────────────────────

def _latest_by_user(queryset, user_field='user_id'):
    latest = {}
    for obj in queryset:
        latest.setdefault(getattr(obj, user_field), obj)
    return latest


def mandatory_guideline_map(scope):
    """{(department_id, type): eng so'nggi amaldagi MandatoryGuideline}."""
    # Tanlov qoidasi companies.guidelines.current_mandatory_guidelines bilan bir xil,
    # lekin barcha boshqarmalar uchun bitta so'rovda.
    if not scope.departments:
        return {}
    candidates = (
        MandatoryGuideline.objects.filter(
            department_id__in=scope.departments_by_id.keys(),
            is_active=True,
            is_stopped=False,
            start_time__lte=scope.now,
            # 00:00 da saqlangan tugash sanalari kun oxirigacha faol
            active_until__gte=scope.now - datetime.timedelta(days=1),
        )
        .order_by('-created_at', '-pk')
    )
    result = {}
    for guideline in candidates:
        key = (guideline.department_id, guideline.guideline_type)
        if key not in result and guideline.is_currently_active:
            result[key] = guideline
    return result


def entry_dispatch_map(scope):
    """{department_id: joriy kirish yo'riqnomasi yuborilishi} — current_entry_dispatch bilan bir xil qoida."""
    if not scope.departments:
        return {}
    result = {}
    dispatches = (
        GuidelineDispatch.objects.filter(
            guideline__department_id__in=scope.departments_by_id.keys(), is_active=True, is_stopped=False,
        )
        .select_related('guideline')
        .order_by('-sent_at', '-pk')
    )
    for dispatch in dispatches:
        result.setdefault(dispatch.guideline.department_id, dispatch)
    return result


def entry_receipts(scope, user_ids):
    """{user_id: joriy yuborilishdagi qabul yozuvi}."""
    dispatch_map = entry_dispatch_map(scope)
    if not user_ids or not dispatch_map:
        return dispatch_map, {}
    receipts = {
        (r.user_id, r.dispatch_id): r
        for r in GuidelineDispatchRecipient.objects.filter(
            user_id__in=user_ids, dispatch_id__in=[d.pk for d in dispatch_map.values()]
        )
    }
    return dispatch_map, receipts


def compute_org_metrics(scope):
    """Hududdagi barcha korxonalar uchun ko'rsatkichlar; so'rovlar soni korxonalar soniga bog'liq emas."""
    user_ids = list(scope.staff_by_user.keys())
    entry_ack = set()
    mandatory_ack = set()
    ppe_ok = set()
    medical_ok = set()
    violations_active = defaultdict(int)
    violations_total = defaultdict(int)
    certs = defaultdict(int)

    if user_ids:
        dispatch_map, receipts = entry_receipts(scope, user_ids)
        for profile in scope.staff:
            department = scope.department_of(profile)
            dispatch = dispatch_map.get(department.pk) if department else None
            receipt = receipts.get((profile.user_id, dispatch.pk)) if dispatch else None
            if receipt and receipt.is_acknowledged:
                entry_ack.add(profile.user_id)
        guideline_map = mandatory_guideline_map(scope)
        mandatory_ack = set(
            MandatoryGuidelineReceipt.objects.filter(
                guideline_id__in=[g.pk for g in guideline_map.values()],
                user_id__in=user_ids,
                is_acknowledged=True,
            ).values_list('user_id', 'guideline_id')
        )
        ppe_ok = set(
            PPEIssue.objects.filter(employee_id__in=user_ids, status='accepted', expiration_date__gte=scope.today)
            .values_list('employee_id', flat=True)
        )
        medical_ok = set(
            EmployeeMedicalRecord.objects.filter(user_id__in=user_ids, end_date__gte=scope.today)
            .values_list('user_id', flat=True)
        )
        for employee_id, is_active in Violation.objects.filter(employee_id__in=user_ids).values_list('employee_id', 'is_active'):
            violations_total[employee_id] += 1
            if is_active:
                violations_active[employee_id] += 1
        for cert_user_id in EmployeeCertificate.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True):
            certs[cert_user_id] += 1
    else:
        guideline_map = {}

    metrics = {}
    for org in scope.orgs:
        profiles = scope.staff_by_org.get(org.pk, [])
        total = len(profiles)
        mandatory_done = mandatory_needed = 0
        for profile in profiles:
            department = scope.department_of(profile)
            for type_key, _ in MANDATORY_TYPES:
                mandatory_needed += 1
                guideline = guideline_map.get((department.pk, type_key)) if department else None
                if guideline and (profile.user_id, guideline.pk) in mandatory_ack:
                    mandatory_done += 1
        uids = [p.user_id for p in profiles]
        entry_rate = _pct(sum(1 for u in uids if u in entry_ack), total)
        mandatory_rate = _pct(mandatory_done, mandatory_needed)
        practice_rate = _pct(sum(1 for p in profiles if p.practice_qualified), total)
        medical_rate = _pct(sum(1 for u in uids if u in medical_ok), total)
        ppe_rate = _pct(sum(1 for u in uids if u in ppe_ok), total)
        active_viol = sum(violations_active[u] for u in uids)
        index = round(
            entry_rate * 0.25 + mandatory_rate * 0.25 + practice_rate * 0.20 + medical_rate * 0.15 + ppe_rate * 0.15
        ) - min(15, active_viol * 3)
        index = max(0, min(100, index)) if total else 0
        status_key, status_label, status_tone = safety_status(index, bool(total))
        supervisor = scope.org_supervisor(org)
        metrics[org.pk] = {
            'org': org,
            'organization_name': org.organization_name or org.full_name,
            'leader_name': org.full_name,
            'leader_phone': org.phone_number or org.user.username,
            'industry_name': org.industry.name if org.industry_id else 'Soha ko‘rsatilmagan',
            'region_name': org.region.name if org.region_id else 'Hudud belgilanmagan',
            'supervisor_name': _person_name(supervisor),
            'supervisor_phone': _person_phone(supervisor),
            'departments_count': sum(1 for d in scope.departments if d.leader_id == org.pk),
            'total_workers': total,
            'entry_rate': entry_rate,
            'mandatory_rate': mandatory_rate,
            'practice_rate': practice_rate,
            'medical_rate': medical_rate,
            'ppe_rate': ppe_rate,
            'active_violations': active_viol,
            'total_violations': sum(violations_total[u] for u in uids),
            'total_certs': sum(certs[u] for u in uids),
            'safety_index': index,
            'status_key': status_key,
            'status_label': status_label,
            'status_tone': status_tone,
            'badge_class': TONE_BADGES[status_tone],
            'is_active': org.user.is_active,
        }
    return metrics


def region_summary(scope, metrics):
    total_workers = sum(m['total_workers'] for m in metrics.values())

    def weighted(key):
        if not total_workers:
            return 0
        return round(sum(m[key] * m['total_workers'] for m in metrics.values()) / total_workers)

    with_workers = [m for m in metrics.values() if m['total_workers']]
    return {
        'total_orgs': len(metrics),
        'total_workers': total_workers,
        'avg_index': round(sum(m['safety_index'] for m in with_workers) / len(with_workers)) if with_workers else 0,
        'entry_rate': weighted('entry_rate'),
        'mandatory_rate': weighted('mandatory_rate'),
        'practice_rate': weighted('practice_rate'),
        'medical_rate': weighted('medical_rate'),
        'ppe_rate': weighted('ppe_rate'),
        'active_violations': sum(m['active_violations'] for m in metrics.values()),
        'total_certs': sum(m['total_certs'] for m in metrics.values()),
        'risk_orgs': sum(1 for m in metrics.values() if m['status_key'] == 'risk'),
        'high_orgs': sum(1 for m in metrics.values() if m['status_key'] == 'high'),
    }


def build_company_rows(scope, metrics):
    rows = []
    for m in sorted(metrics.values(), key=lambda item: (-item['safety_index'], item['organization_name'])):
        rows.append(make_row(
            primary=m['organization_name'],
            primary_sub=f"Rahbar: {m['leader_name']} · {m['leader_phone']}",
            category=m['industry_name'],
            category_sub=f"{m['total_workers']} nafar xodim · {m['departments_count']} boshqarma",
            supervisor=m['supervisor_name'],
            supervisor_phone=m['supervisor_phone'],
            metric=f"{m['safety_index']}%",
            metric_sub=f"Faol qoidabuzarlik: {m['active_violations']}",
            progress=m['safety_index'],
            status_key=m['status_key'],
            status_label=m['status_label'],
            status_tone=m['status_tone'],
            detail_url=reverse('inspection:company-detail', args=[m['org'].pk]),
        ))
    return rows


# ─────────────────────────────────────────────────────────────
#  Yo'riqnomalar
# ─────────────────────────────────────────────────────────────

def build_entry_rows(scope, profiles):
    dispatch_map, receipts = entry_receipts(scope, [p.user_id for p in profiles])
    rows = []
    for profile in profiles:
        department = scope.department_of(profile)
        dispatch = dispatch_map.get(department.pk) if department else None
        receipt = receipts.get((profile.user_id, dispatch.pk)) if dispatch else None
        if not dispatch:
            status = ('missing', 'Yo‘riqnoma yo‘q', 'slate')
            metric, metric_sub = DASH, 'Boshqarmada faol kirish yo‘riqnomasi yo‘q'
        elif receipt and receipt.is_acknowledged:
            status = ('done', 'Tanishgan', 'emerald')
            metric, metric_sub = _fmt_date(receipt.acknowledged_at), dispatch.guideline.name
        else:
            status = ('pending', 'Tanishmagan', 'rose')
            metric, metric_sub = DASH, dispatch.guideline.name
        rows.append(make_row(
            **scope.person_fields(profile), metric=metric, metric_sub=metric_sub,
            status_key=status[0], status_label=status[1], status_tone=status[2],
        ))
    return rows


def build_mandatory_rows(scope, profiles, guideline_type=None):
    guideline_map = mandatory_guideline_map(scope)
    user_ids = [p.user_id for p in profiles]
    receipts = {}
    if user_ids and guideline_map:
        receipts = {
            (r.user_id, r.guideline_id): r
            for r in MandatoryGuidelineReceipt.objects.filter(
                user_id__in=user_ids, guideline_id__in=[g.pk for g in guideline_map.values()]
            )
        }
    types = [(k, label) for k, label in MANDATORY_TYPES if not guideline_type or k == guideline_type]
    rows = []
    for profile in profiles:
        department = scope.department_of(profile)
        done, available, parts, last_ack = 0, 0, [], None
        for type_key, label in types:
            guideline = guideline_map.get((department.pk, type_key)) if department else None
            if not guideline:
                parts.append(f'{label}: yo‘q')
                continue
            available += 1
            receipt = receipts.get((profile.user_id, guideline.pk))
            if receipt and receipt.is_acknowledged:
                done += 1
                parts.append(f'{label}: ✓')
                last_ack = max(filter(None, [last_ack, receipt.acknowledged_at]), default=None)
            else:
                parts.append(f'{label}: kutilmoqda')
        if not available:
            status = ('missing', 'Yo‘riqnoma yo‘q', 'slate')
        elif done == len(types):
            status = ('done', 'To‘liq tanishgan', 'emerald')
        elif done:
            status = ('partial', 'Qisman', 'amber')
        else:
            status = ('pending', 'Tanishmagan', 'rose')
        if len(types) == 1:
            metric = _fmt_date(last_ack) if done else DASH
            metric_sub = parts[0]
        else:
            metric = f'{done}/{len(types)}'
            metric_sub = ' · '.join(parts)
        rows.append(make_row(
            **scope.person_fields(profile), metric=metric, metric_sub=metric_sub,
            progress=_pct(done, len(types)) if len(types) > 1 else None,
            status_key=status[0], status_label=status[1], status_tone=status[2],
        ))
    return rows


def build_internal_rows(scope, profiles):
    user_ids = [p.user_id for p in profiles]
    latest = _latest_by_user(
        SectionInternalGuidelineRecipient.objects.filter(user_id__in=user_ids)
        .select_related('dispatch__guideline')
        .order_by('user_id', '-dispatch__sent_at', '-pk')
    ) if user_ids else {}
    rows = []
    for profile in profiles:
        receipt = latest.get(profile.user_id)
        if receipt and receipt.is_acknowledged:
            status = ('done', 'Tanishgan', 'emerald')
            metric = _fmt_date(receipt.acknowledged_at)
        elif receipt and receipt.dispatch.is_currently_active:
            status = ('pending', 'Kutilmoqda', 'amber')
            metric = DASH
        elif receipt:
            status = ('overdue', 'Muddatida tanishmagan', 'rose')
            metric = DASH
        else:
            status = ('missing', 'Yuborilmagan', 'slate')
            metric = DASH
        rows.append(make_row(
            **scope.person_fields(profile), metric=metric,
            metric_sub=receipt.dispatch.guideline.name if receipt else 'Bo‘lim yo‘riqnomasi yo‘q',
            status_key=status[0], status_label=status[1], status_tone=status[2],
        ))
    return rows


def build_profession_rows(scope, profiles):
    memberships = [scope.memberships_by_user.get(p.user_id) for p in profiles]
    membership_ids = [m.pk for m in memberships if m]
    receipts = {
        r.membership_id: r
        for r in ProfessionGuidelineReceipt.objects.filter(membership_id__in=membership_ids)
    } if membership_ids else {}
    rows = []
    for profile, membership in zip(profiles, memberships):
        profession = membership.profession if membership and membership.profession_id else None
        receipt = receipts.get(membership.pk) if membership else None
        if not profession:
            status, metric_sub = ('noprof', 'Kasb biriktirilmagan', 'slate'), DASH
        elif not profession.nizom_file:
            status, metric_sub = ('missing', 'Kasb yo‘riqnomasi yo‘q', 'slate'), profession.name
        elif receipt and receipt.is_acknowledged and receipt.profession_id == profession.pk:
            status, metric_sub = ('done', 'Tanishgan', 'emerald'), profession.name
        else:
            status, metric_sub = ('pending', 'Tanishmagan', 'rose'), profession.name
        rows.append(make_row(
            **scope.person_fields(profile),
            metric=_fmt_date(receipt.acknowledged_at) if status[0] == 'done' else DASH,
            metric_sub=metric_sub,
            status_key=status[0], status_label=status[1], status_tone=status[2],
        ))
    return rows


# ─────────────────────────────────────────────────────────────
#  Stajirovka va bilimni baholash
# ─────────────────────────────────────────────────────────────

def build_practice_rows(scope, profiles):
    user_ids = [p.user_id for p in profiles]
    if not user_ids or not scope.sections_by_id:
        return []
    assignments = (
        SectionWorkPracticeAssignee.objects.filter(
            user_id__in=user_ids, practice__section_id__in=scope.sections_by_id.keys()
        )
        .select_related('practice__responsible_user__profile', 'practice__section')
        .order_by('-practice__start_time')
    )
    rows = []
    for item in assignments:
        profile = scope.staff_by_user[item.user_id]
        practice = item.practice
        fields = scope.person_fields(profile)
        fields['category'] = practice.name
        fields['category_sub'] = practice.section.name
        fields['supervisor'] = _person_name(practice.responsible_user)
        fields['supervisor_phone'] = _person_phone(practice.responsible_user)
        start, end = practice.start_time, practice.end_time
        total_days = max((end - start).days, 1)
        if practice.closed_at:
            status = ('closed', 'Yakunlangan', 'emerald')
            progress, sub = 100, f'Yopilgan: {_fmt_date(practice.closed_at)}'
        elif scope.now < start:
            status = ('upcoming', 'Boshlanmagan', 'slate')
            progress, sub = 0, f'{(start - scope.now).days} kundan so‘ng boshlanadi'
        elif scope.now <= end:
            status = ('active', 'Jarayonda', 'sky')
            progress = min(100, _pct((scope.now - start).days, total_days))
            sub = f'{(end - scope.now).days} kun qoldi'
        else:
            status = ('overdue', 'Muddati o‘tgan', 'rose')
            progress, sub = 100, 'Yakuniy xulosa kiritilmagan'
        if not item.accepted_by_responsible and status[0] in {'active', 'upcoming'}:
            sub = f'{sub} · ustoz tasdiqlamagan'
        rows.append(make_row(
            **fields, metric=f'{_fmt_date(start)} – {_fmt_date(end)}', metric_sub=sub, progress=progress,
            status_key=status[0], status_label=status[1], status_tone=status[2],
        ))
    return rows


def build_test_rows(scope, profiles, kind=None):
    user_ids = [p.user_id for p in profiles]
    if not user_ids:
        return []
    rows = []
    if kind in (None, '', 'practice'):
        attempts = (
            WorkPracticeTestAttempt.objects.filter(user_id__in=user_ids)
            .select_related('test', 'practice__responsible_user__profile')
            .order_by('-started_at')
        )
        for attempt in attempts:
            threshold = getattr(attempt.test, 'pass_percentage', None) or DEFAULT_PRACTICE_PASS_PERCENT
            rows.append(_test_row(
                scope, scope.staff_by_user[attempt.user_id], attempt, attempt.test.name, 'Stajirovka yakuniy testi',
                attempt.practice.responsible_user, threshold,
            ))
    if kind in (None, '', 'assessment'):
        attempts = (
            DepartmentAssessmentAttempt.objects.filter(user_id__in=user_ids)
            .select_related('assessment__department__supervisor__profile')
            .order_by('-started_at')
        )
        for attempt in attempts:
            rows.append(_test_row(
                scope, scope.staff_by_user[attempt.user_id], attempt, attempt.assessment.name, 'Bilimni baholash testi',
                attempt.assessment.department.supervisor, ASSESSMENT_PASS_PERCENT,
            ))
    rows.sort(key=lambda row: row['_sort'], reverse=True)
    return rows


def _test_row(scope, profile, attempt, test_name, kind_label, responsible, threshold):
    fields = scope.person_fields(profile)
    fields['category'] = test_name
    fields['category_sub'] = f'{kind_label} · o‘tish chegarasi {threshold}%'
    fields['supervisor'] = _person_name(responsible)
    fields['supervisor_phone'] = _person_phone(responsible)
    if not attempt.finished_at or attempt.score is None:
        status, metric = ('progress', 'Yakunlanmagan', 'slate'), DASH
    elif attempt.score >= threshold:
        status, metric = ('passed', 'O‘tdi', 'emerald'), f'{attempt.score}%'
    else:
        status, metric = ('failed', 'O‘tmadi', 'rose'), f'{attempt.score}%'
    row = make_row(
        **fields, metric=metric, metric_sub=_fmt_date(attempt.finished_at or attempt.started_at),
        progress=attempt.score if attempt.score is not None else None,
        status_key=status[0], status_label=status[1], status_tone=status[2],
    )
    row['_sort'] = attempt.started_at
    return row


# ─────────────────────────────────────────────────────────────
#  Qoidabuzarliklar, IHV, sertifikat, tibbiy ko'rik
# ─────────────────────────────────────────────────────────────

def build_violation_rows(scope, profiles):
    user_ids = [p.user_id for p in profiles]
    if not user_ids:
        return []
    violations = (
        Violation.objects.filter(employee_id__in=user_ids)
        .select_related('violation_type', 'issued_by__profile')
        .order_by('-date', '-created_at')
    )
    rows = []
    for violation in violations:
        fields = scope.person_fields(scope.staff_by_user[violation.employee_id])
        fields['category'] = violation.violation_type.name
        fields['category_sub'] = _fmt_date(violation.date)
        fields['supervisor'] = _person_name(violation.issued_by)
        fields['supervisor_phone'] = _person_phone(violation.issued_by)
        reason = violation.reason or ''
        if violation.is_active:
            status = ('active', 'Faol', 'rose')
            sub = 'Tushuntirish xati olinmagan'
        else:
            status = ('resolved', 'Chora ko‘rilgan', 'emerald')
            sub = 'Tushuntirish xati olingan'
        rows.append(make_row(
            **fields, metric=(reason[:70] + '…') if len(reason) > 70 else reason, metric_sub=sub,
            status_key=status[0], status_label=status[1], status_tone=status[2], search_extra=reason,
        ))
    return rows


def build_ppe_rows(scope, profiles):
    user_ids = [p.user_id for p in profiles]
    issues = defaultdict(list)
    if user_ids:
        for issue in PPEIssue.objects.filter(employee_id__in=user_ids).select_related('ppe_type'):
            issues[issue.employee_id].append(issue)
    rows = []
    for profile in profiles:
        items = issues.get(profile.user_id, [])
        valid = [i for i in items if i.status == 'accepted' and i.expiration_date >= scope.today]
        expired = [i for i in items if i.expiration_date < scope.today]
        pending = [i for i in items if i.status != 'accepted' and i.expiration_date >= scope.today]
        if not items:
            status = ('none', 'Berilmagan', 'rose')
        elif valid and not expired and not pending:
            status = ('ok', 'Ta’minlangan', 'emerald')
        elif valid:
            status = ('partial', 'Qisman', 'amber')
        else:
            status = ('expired', 'Muddati o‘tgan', 'rose')
        sub_parts = []
        if expired:
            sub_parts.append(f'{len(expired)} ta muddati o‘tgan')
        if pending:
            sub_parts.append(f'{len(pending)} ta qabul qilinmagan')
        rows.append(make_row(
            **scope.person_fields(profile),
            metric=f'{len(valid)} ta amalda' if items else DASH,
            metric_sub=' · '.join(sub_parts) or ', '.join(sorted({i.ppe_type.name for i in valid}))[:80],
            status_key=status[0], status_label=status[1], status_tone=status[2],
        ))
    return rows


def build_certificate_rows(scope, profiles):
    user_ids = [p.user_id for p in profiles]
    if not user_ids:
        return []
    rows = []
    for cert in EmployeeCertificate.objects.filter(user_id__in=user_ids).select_related('certificate_type').order_by('-created_at'):
        fields = scope.person_fields(scope.staff_by_user[cert.user_id])
        fields['category'] = cert.certificate_type.name
        fields['category_sub'] = fields['category_sub'] or ''
        if cert.file:
            fields['detail_url'] = cert.file.url
        rows.append(make_row(
            **fields, metric=_fmt_date(cert.created_at), metric_sub='Yuklangan sana',
            status_key='uploaded', status_label='Tasdiqlangan', status_tone='emerald',
            detail_external=bool(cert.file),
        ))
    return rows


def build_medical_rows(scope, profiles):
    user_ids = [p.user_id for p in profiles]
    latest = _latest_by_user(
        EmployeeMedicalRecord.objects.filter(user_id__in=user_ids).order_by('user_id', '-end_date', '-pk')
    ) if user_ids else {}
    rows = []
    for profile in profiles:
        record = latest.get(profile.user_id)
        if not record:
            status, metric, sub = ('none', 'Ko‘rikdan o‘tmagan', 'rose'), DASH, 'Tibbiy ma’lumot kiritilmagan'
        else:
            days = (record.end_date - scope.today).days
            metric = f'{_fmt_date(record.end_date)} gacha'
            if days < 0:
                status, sub = ('expired', 'Muddati o‘tgan', 'rose'), f'{-days} kun oldin tugagan'
            elif days <= 30:
                status, sub = ('soon', 'Tugash arafasida', 'amber'), f'{days} kun qoldi'
            else:
                status, sub = ('ok', 'Amalda', 'emerald'), f'{days} kun qoldi'
        rows.append(make_row(
            **scope.person_fields(profile), metric=metric, metric_sub=sub,
            status_key=status[0], status_label=status[1], status_tone=status[2],
        ))
    return rows


def build_staff_rows(scope, profiles):
    """Korxona sahifasidagi xodimlar tarkibi (umumiy ruxsat holati)."""
    rows = []
    for profile in profiles:
        if profile.is_blocked_by_violations:
            status = ('blocked', 'Chetlashtirilgan', 'rose')
        elif profile.practice_qualified:
            status = ('qualified', 'Mustaqil ishga ruxsat', 'emerald')
        else:
            status = ('pending', 'Ruxsat berilmagan', 'amber')
        rows.append(make_row(
            **scope.person_fields(profile),
            metric=profile.phone_number or profile.user.username,
            metric_sub=profile.get_employment_status_display(),
            status_key=status[0], status_label=status[1], status_tone=status[2],
        ))
    return rows
