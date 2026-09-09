def get_unread_notifications_count(user):
    """O'qilmagan barcha tizim bildirishnomalari soni (yo'riqnomalar, testlar, tizim xabarlari)."""
    if not user.is_authenticated:
        return 0

    from companies.models import (
        GuidelineDispatchRecipient, SectionInternalGuidelineRecipient,
        DepartmentAssessmentNotification, SectionWorkPracticeMessageReceipt
    )
    from accounts.models import SystemNotification

    dept_count = GuidelineDispatchRecipient.objects.filter(user=user, is_acknowledged=False).count()
    internal_count = SectionInternalGuidelineRecipient.objects.filter(user=user, is_acknowledged=False).count()
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
    for r in GuidelineDispatchRecipient.objects.filter(user=user).select_related('dispatch__guideline'):
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
    for r in SectionInternalGuidelineRecipient.objects.filter(user=user).select_related('dispatch__guideline'):
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
        notifications.append({
            'id': f"sn_{sn.id}",
            'title': sn.title,
            'message': sn.message,
            'is_read': sn.is_read,
            'created_at': sn.created_at,
            'url': sn.url or '#',
            'icon': 'bi-bell',
            'type': sn.type
        })
        
    # Sort by created_at desc
    notifications.sort(key=lambda x: x['created_at'], reverse=True)
    return notifications

