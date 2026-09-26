def get_unread_notifications_count(user):
    """O'qilmagan barcha tizim bildirishnomalari soni (yo'riqnomalar, testlar, tizim xabarlari)."""
    if not user.is_authenticated:
        return 0

    from companies.models import (
        GuidelineDispatchRecipient, SectionInternalGuidelineRecipient,
        DepartmentAssessmentNotification, SectionWorkPracticeMessageReceipt
    )
    from accounts.models import SystemNotification

    from companies.guidelines import current_entry_receipt, current_internal_receipts

    # Faqat joriy (eng so'nggi faol) yo'riqnomalar — eski versiyalar dublikat sanalmaydi
    entry_receipt = current_entry_receipt(user)
    dept_count = 1 if entry_receipt and not entry_receipt.is_acknowledged else 0
    internal_count = sum(1 for receipt in current_internal_receipts(user) if not receipt.is_acknowledged)
    assessment_count = DepartmentAssessmentNotification.objects.filter(user=user, is_confirmed=False).count()
    practice_msg_count = SectionWorkPracticeMessageReceipt.objects.filter(user=user, is_read=False).count()
    system_count = SystemNotification.objects.filter(user=user, is_read=False).count()
    
    return dept_count + internal_count + assessment_count + practice_msg_count + system_count


def get_unread_section_messages_count(user):
    """Bo'lim chatidagi o'qilmagan xabarlar soni."""
    if not user.is_authenticated:
        return 0
    from companies.models import SectionMessageReceipt
    return SectionMessageReceipt.objects.filter(user=user, is_read=False).count()


def get_all_notifications(user):
    """Barcha bildirishnomalarni yagona ro'yxatga birlashtirish."""
    if not user.is_authenticated:
        return []
        
    from companies.models import (
        GuidelineDispatchRecipient, SectionInternalGuidelineRecipient,
        DepartmentAssessmentNotification, SectionWorkPracticeMessageReceipt,
        SectionMessageReceipt
    )
    from accounts.models import SystemNotification
    
    notifications = []
    
    # 1. Guideline Dispatch
    from companies.guidelines import current_entry_receipt, current_internal_receipts

    entry_receipt = current_entry_receipt(user)
    for r in ([entry_receipt] if entry_receipt else []):
        notifications.append({
            'id': f"gd_{r.id}",
            'title': "Kirish yo'riqnomasi qabul qiling",
            'message': r.dispatch.guideline.name,
            'is_read': r.is_acknowledged,
            'created_at': r.dispatch.sent_at,
            'url': '/kirish-yoriknomam/',
            'icon': 'bi-file-earmark-pdf',
            'type': 'guideline'
        })
        
    # 2. Internal Guidelines
    for r in current_internal_receipts(user):
        notifications.append({
            'id': f"ig_{r.id}",
            'title': "Ichki yo'riqnoma qabul qiling",
            'message': r.dispatch.guideline.name,
            'is_read': r.is_acknowledged,
            'created_at': r.dispatch.sent_at,
            'url': '/xabarlarim/',
            'icon': 'bi-file-earmark-text',
            'type': 'guideline'
        })
        
    # 3. Department Assessments
    for r in DepartmentAssessmentNotification.objects.filter(user=user).select_related('assessment'):
        notifications.append({
            'id': f"da_{r.id}",
            'title': "Yangi test joriy qilindi",
            'message': r.assessment.name,
            'is_read': r.is_confirmed,
            'created_at': r.created_at,
            'url': '/bilim-baholash/kirish/',
            'icon': 'bi-journal-check',
            'type': 'assessment'
        })
        
    # 4. Work Practice Messages
    for r in SectionWorkPracticeMessageReceipt.objects.filter(user=user).select_related('message'):
        notifications.append({
            'id': f"pm_{r.id}",
            'title': "Amaliyot bo'yicha xabar",
            'message': r.message.title,
            'is_read': r.is_read,
            'created_at': r.message.created_at,
            'url': '/ish-amaliyotlari/',
            'icon': 'bi-chat-left-text',
            'type': 'message'
        })

    # 5. Section Direct Messages
    for r in SectionMessageReceipt.objects.filter(user=user).select_related('message'):
        notifications.append({
            'id': f"sm_{r.id}",
            'title': f"Bo'lim xabarnomasi: {r.message.title}",
            'message': r.message.body[:100] + ('...' if len(r.message.body) > 100 else ''),
            'is_read': r.is_read,
            'created_at': r.message.created_at,
            'url': '/xabarnomalar/',
            'icon': 'bi-chat-dots',
            'type': 'message'
        })
        
    # 6. System Notifications
    for sn in SystemNotification.objects.filter(user=user):
        icon = 'bi-bell-fill'
        badge_color = 'bg-slate-100 text-slate-800'
        if sn.type == 'violation':
            icon = 'bi-exclamation-triangle-fill'
            badge_color = 'bg-rose-100 text-rose-800'
        elif sn.type == 'permission':
            icon = 'bi-shield-check'
            badge_color = 'bg-emerald-100 text-emerald-800'
        elif sn.type == 'test':
            icon = 'bi-card-checklist'
            badge_color = 'bg-blue-100 text-blue-800'
        elif sn.type == 'practice':
            icon = 'bi-briefcase-fill'
            badge_color = 'bg-indigo-100 text-indigo-800'
        elif sn.type == 'guideline':
            icon = 'bi-file-earmark-text'
            badge_color = 'bg-teal-100 text-teal-800'

        notifications.append({
            'id': f"sn_{sn.id}",
            'title': sn.title,
            'message': sn.message,
            'is_read': sn.is_read,
            'created_at': sn.created_at,
            'url': sn.url or '#',
            'icon': icon,
            'type': sn.type,
            'badge_color': badge_color
        })
        
    # Sort by created_at desc
    notifications.sort(key=lambda x: x['created_at'], reverse=True)
    return notifications


def send_action_notification(
    title: str,
    message: str,
    notif_type: str = 'system',
    url: str = '#',
    section=None,
    department=None,
    organization=None,
    target_users=None,
    exclude_users=None
):
    """
    Mas'ul xodimlarning bajargan ishlari bo'yicha rahbarlar va nazoratchilarga bildirishnoma yuborish:
    1. Tashkilot rahbari (Direktor)
    2. Boshqarma nazoratchisi (Mehnat muhofazasi va texnika xavfsizligi muhandisi - OTX)
    3. Bo'lim boshlig'i (Section admin)
    4. Qo'shimcha belgilangan target_users (masalan xodimning o'zi)
    """
    from accounts.models import UserProfile, SystemNotification
    from django.contrib.auth import get_user_model
    User = get_user_model()

    recipients = set()

    # Agar target_users berilgan bo'lsa
    if target_users:
        for u in target_users:
            if isinstance(u, User):
                recipients.add(u)
            elif hasattr(u, 'user'):
                recipients.add(u.user)

    # Section berilgan bo'lsa
    if section:
        if not department and section.department:
            department = section.department
        # 1. Bo'lim boshlig'i
        if section.supervisor:
            recipients.add(section.supervisor)
        sec_admins = UserProfile.objects.filter(
            section=section, role=UserProfile.ROLE_SECTION_ADMIN
        ).select_related('user')
        for sa in sec_admins:
            recipients.add(sa.user)

    # Department berilgan bo'lsa
    if department:
        # 2. Boshqarma nazoratchisi (Mehnat muhofazasi va texnika xavfsizligi muhandisi)
        if department.supervisor:
            recipients.add(department.supervisor)
        dept_admins = UserProfile.objects.filter(
            department=department, role=UserProfile.ROLE_DEPARTMENT_ADMIN
        ).select_related('user')
        for da in dept_admins:
            recipients.add(da.user)

        # 3. Tashkilot rahbari (Direktor)
        if department.leader and department.leader.user:
            recipients.add(department.leader.user)

    # Agar organization aniq berilgan bo'lsa
    if organization:
        if isinstance(organization, UserProfile) and organization.user:
            recipients.add(organization.user)
        elif hasattr(organization, 'leader') and organization.leader and organization.leader.user:
            recipients.add(organization.leader.user)

    # Agar hali ham tashkilot rahbari qo'shilmagan bo'lsa
    if not any(getattr(getattr(r, 'profile', None), 'role', None) == UserProfile.ROLE_ORG_LEADER for r in recipients):
        if section and hasattr(section, 'department') and section.department.leader:
            recipients.add(section.department.leader.user)
        elif department and department.leader:
            recipients.add(department.leader.user)
        else:
            first_user = next(iter(recipients), None)
            if first_user and hasattr(first_user, 'profile') and first_user.profile.organization:
                recipients.add(first_user.profile.organization.user)

    # Exclude users
    if exclude_users:
        exclude_set = set()
        for eu in exclude_users:
            if isinstance(eu, User):
                exclude_set.add(eu)
            elif hasattr(eu, 'user'):
                exclude_set.add(eu.user)
        recipients = recipients - exclude_set

    notifications_to_create = []
    for user in recipients:
        notifications_to_create.append(
            SystemNotification(
                user=user,
                title=title,
                message=message,
                type=notif_type,
                url=url
            )
        )

    if notifications_to_create:
        SystemNotification.objects.bulk_create(notifications_to_create)

    return len(notifications_to_create)

