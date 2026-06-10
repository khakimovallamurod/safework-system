from companies.models import GuidelineDispatchRecipient


WORKER_ENTRY_GUIDELINE_ALLOWED_URLS = {
    'worker-entry-guidelines',
    'guideline-pdf',
    'guideline-acknowledge',
    'logout',
    'serve-stored-media',
}


def get_pending_entry_guidelines_count(user):
    if not user.is_authenticated:
        return 0
        
    profile = getattr(user, 'profile', None)
    if not profile:
        return 0
        
    from accounts.models import UserProfile
    if profile.role not in {UserProfile.ROLE_WORKER, UserProfile.ROLE_SECTION_ADMIN}:
        return 0
        
    if not profile.department_id:
        return 0
        
    from companies.models import GuidelineDispatch, GuidelineDispatchRecipient
    
    active_dispatch = GuidelineDispatch.objects.filter(
        guideline__department_id=profile.department_id,
        is_active=True
    ).first()
    
    if not active_dispatch:
        return 0
        
    receipt = GuidelineDispatchRecipient.objects.filter(
        dispatch=active_dispatch,
        user=user
    ).first()
    
    if not receipt:
        kind = GuidelineDispatchRecipient.KIND_SECTION if profile.role == UserProfile.ROLE_SECTION_ADMIN else GuidelineDispatchRecipient.KIND_WORKER
        receipt = GuidelineDispatchRecipient.objects.create(
            dispatch=active_dispatch,
            user=user,
            section_id=profile.section_id,
            recipient_kind=kind
        )
        
    return 1 if not receipt.is_acknowledged else 0


def get_worker_entry_guideline_context(user, is_entry_guideline_user):
    pending_count = get_pending_entry_guidelines_count(user) if is_entry_guideline_user else 0
    return {
        'pending_entry_guidelines_count': pending_count,
        'worker_entry_guideline_locked': is_entry_guideline_user and pending_count > 0,
    }
