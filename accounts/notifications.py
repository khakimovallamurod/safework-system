def get_unread_notifications_count(user):
    """O'qilmagan kirish va ichki yo'riqnomalar soni."""
    if not user.is_authenticated:
        return 0

    from companies.models import GuidelineDispatchRecipient, SectionInternalGuidelineRecipient

    dept_count = GuidelineDispatchRecipient.objects.filter(user=user, is_acknowledged=False).count()
    internal_count = SectionInternalGuidelineRecipient.objects.filter(
        user=user, is_acknowledged=False
    ).count()
    return dept_count + internal_count
