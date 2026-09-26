"""Yo'riqnomalar uchun umumiy vaqt va tanlash (selector) yordamchilari.

Barcha yo'riqnoma turlari (kirish, majburiy, kasb, ichki) uchun:
  * faollik oynasi (boshlanish <= hozir <= tugash) bir xil hisoblanadi;
  * "necha kun qoldi" mahalliy kalendar kunlari bo'yicha hisoblanadi;
  * xodimga har bir tur bo'yicha faqat bitta — eng so'nggi faol versiya ko'rsatiladi.
"""

import datetime

from django.utils import timezone


# Tugash vaqti formadagi <input type="date"> dan kelganda soat 00:00 bo'lib saqlanadi.
# Bunday qiymat "shu kun oxirigacha" deb talqin qilinadi, aks holda yo'riqnoma
# oxirgi kuni boshlanishi bilanoq "Muddati tugagan" bo'lib qoladi.
def effective_end(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    local = timezone.localtime(value)
    if local.time() == datetime.time.min:
        return local.replace(hour=23, minute=59, second=59, microsecond=999999)
    return value


def normalize_end_of_day(value):
    """Formadan kelgan tugash vaqtini kun oxiriga (23:59:59) o'tkazish."""
    return effective_end(value)


def is_within_window(start, end, now=None):
    now = now or timezone.now()
    if start and now < start:
        return False
    end = effective_end(end)
    if end and now > end:
        return False
    return True


def has_started(start, now=None):
    return not start or (now or timezone.now()) >= start


def is_expired(end, now=None):
    end = effective_end(end)
    return bool(end and (now or timezone.now()) > end)


def days_left(end, now=None):
    """Mahalliy kalendar kunlari bo'yicha qolgan kunlar.

    0  — bugun tugaydi (hali faol), musbat — qolgan kunlar,
    -1 — muddati o'tgan. Faol yo'riqnoma uchun hech qachon manfiy bo'lmaydi.
    """
    if not end:
        return None
    now = now or timezone.now()
    end = effective_end(end)
    if now > end:
        return -1
    return max((timezone.localdate(end) - timezone.localdate(now)).days, 0)


# ---------------------------------------------------------------------------
# Selectorlar
# ---------------------------------------------------------------------------

def mandatory_type_order():
    from companies.models import MandatoryGuideline

    return {
        MandatoryGuideline.TYPE_MEDICAL: 0,
        MandatoryGuideline.TYPE_FIRE: 1,
        MandatoryGuideline.TYPE_ELECTRIC: 2,
    }


def current_mandatory_guidelines(department_id, now=None):
    """Boshqarma uchun har bir tur bo'yicha bittadan — eng so'nggi faol majburiy yo'riqnoma.

    To'xtatilgan (is_stopped) va arxivga o'tgan (is_active=False) versiyalar hisobga olinmaydi.
    Natija tur tartibida (tibbiy, yong'in, elektr) qaytariladi.
    """
    from companies.models import MandatoryGuideline

    if not department_id:
        return []
    now = now or timezone.now()
    candidates = (
        MandatoryGuideline.objects.filter(
            department_id=department_id,
            is_active=True,
            is_stopped=False,
            start_time__lte=now,
            # 00:00 da saqlangan tugash sanalari kun oxirigacha faol — shuning uchun 1 kun zaxira
            active_until__gte=now - datetime.timedelta(days=1),
        )
        .select_related('department')
        .order_by('-created_at', '-pk')
    )
    latest_by_type = {}
    for guideline in candidates:
        if guideline.guideline_type in latest_by_type:
            continue
        if not guideline.is_currently_active:
            continue
        latest_by_type[guideline.guideline_type] = guideline
    order = mandatory_type_order()
    return sorted(latest_by_type.values(), key=lambda item: order.get(item.guideline_type, 99))


def current_entry_dispatch(department_id):
    """Boshqarmaning joriy (eng so'nggi, to'xtatilmagan) kirish yo'riqnomasi yuborilishi."""
    from companies.models import GuidelineDispatch

    if not department_id:
        return None
    return (
        GuidelineDispatch.objects.filter(
            guideline__department_id=department_id,
            is_active=True,
            is_stopped=False,
        )
        .select_related('guideline')
        .order_by('-sent_at', '-pk')
        .first()
    )


def current_entry_receipt(user, create=False):
    """Foydalanuvchining joriy kirish yo'riqnomasi qabul yozuvi (faqat bitta)."""
    from accounts.models import UserProfile
    from companies.models import GuidelineDispatchRecipient

    profile = getattr(user, 'profile', None)
    if not profile or not profile.department_id:
        return None
    dispatch = current_entry_dispatch(profile.department_id)
    if not dispatch:
        return None
    receipt = (
        GuidelineDispatchRecipient.objects.filter(dispatch=dispatch, user=user)
        .select_related('dispatch__guideline', 'section')
        .first()
    )
    if receipt is None and create:
        kind = (
            GuidelineDispatchRecipient.KIND_SECTION
            if profile.role == UserProfile.ROLE_SECTION_ADMIN
            else GuidelineDispatchRecipient.KIND_WORKER
        )
        receipt, _ = GuidelineDispatchRecipient.objects.get_or_create(
            dispatch=dispatch,
            user=user,
            defaults={'section_id': profile.section_id, 'recipient_kind': kind},
        )
        receipt.dispatch = dispatch
    return receipt


def current_internal_receipts(user):
    """Har bir ichki yo'riqnoma bo'yicha faqat eng so'nggi faol yuborilish qabul yozuvi."""
    from companies.models import SectionInternalGuidelineRecipient

    receipts = (
        SectionInternalGuidelineRecipient.objects.filter(
            user=user,
            dispatch__is_active=True,
            dispatch__is_stopped=False,
        )
        .select_related('dispatch__guideline')
        .order_by('-dispatch__sent_at', '-dispatch_id')
    )
    seen = set()
    result = []
    for receipt in receipts:
        guideline_id = receipt.dispatch.guideline_id
        if guideline_id in seen:
            continue
        seen.add(guideline_id)
        result.append(receipt)
    return result


def current_profession_membership(user):
    """Kasb yo'riqnomasi uchun joriy a'zolik (gate, inbox, PDF va qabul uchun yagona tanlov)."""
    from accounts.models import UserProfile
    from companies.models import SectionMembership

    profile = getattr(user, 'profile', None)
    memberships = (
        SectionMembership.objects.filter(user=user, profession__isnull=False, profession__nizom_file__isnull=False)
        .exclude(profession__nizom_file='')
        .select_related('profession', 'section')
        .order_by('-assigned_at', '-pk')
    )
    membership = None
    if profile and profile.section_id:
        membership = memberships.filter(section_id=profile.section_id).first()
    if not membership and profile and profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN:
        membership = memberships.filter(section__isnull=True).first()
    if not membership:
        membership = memberships.first()
    return membership


def profession_guideline_receipt(membership):
    """A'zolik uchun kasb yo'riqnomasi qabul yozuvi; kasb o'zgarsa qabul qayta talab qilinadi."""
    from companies.models import ProfessionGuidelineReceipt

    receipt, _ = ProfessionGuidelineReceipt.objects.get_or_create(
        membership=membership,
        defaults={'profession': membership.profession},
    )
    if receipt.profession_id != membership.profession_id:
        receipt.profession = membership.profession
        receipt.is_acknowledged = False
        receipt.acknowledged_at = None
        receipt.save(update_fields=['profession', 'is_acknowledged', 'acknowledged_at'])
    return receipt
