from django.utils import timezone

from companies.models import GuidelineDispatchRecipient


WORKER_ENTRY_GUIDELINE_ALLOWED_URLS = {
    'worker-entry-guidelines',
    'guideline-pdf',
    'guideline-acknowledge',
    'mandatory-guidelines-inbox',
    'mandatory-guideline-pdf',
    'mandatory-guideline-acknowledge',
    'profession-guideline-inbox',
    'profession-guideline-pdf',
    'profession-guideline-acknowledge',
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
    ).select_related('guideline').first()
    
    if not active_dispatch or not active_dispatch.guideline.is_currently_active:
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


def get_guideline_gate_state(user):
    state = {
        'pending_entry_guidelines_count': 0,
        'pending_mandatory_guidelines_count': 0,
        'pending_profession_guidelines_count': 0,
        'next_guideline_url_name': '',
        'next_mandatory_guideline_type': '',
        'worker_entry_guideline_locked': False,
        'mandatory_guideline_locked': False,
        'profession_guideline_locked': False,
        'has_profession_guideline': False,
    }
    if not user.is_authenticated:
        return state

    profile = getattr(user, 'profile', None)
    from accounts.models import UserProfile
    if not profile or profile.role not in {UserProfile.ROLE_WORKER, UserProfile.ROLE_SECTION_ADMIN}:
        return state

    entry_pending = get_pending_entry_guidelines_count(user)
    state['pending_entry_guidelines_count'] = entry_pending
    if entry_pending:
        state['worker_entry_guideline_locked'] = True
        state['next_guideline_url_name'] = 'worker-entry-guidelines'
        return state

    if profile.department_id:
        from companies.models import MandatoryGuideline, MandatoryGuidelineReceipt
        active_guidelines = list(MandatoryGuideline.objects.filter(
            department_id=profile.department_id,
            start_time__lte=timezone.now(),
            active_until__gte=timezone.now(),
        ))
        type_order = {
            MandatoryGuideline.TYPE_MEDICAL: 0,
            MandatoryGuideline.TYPE_FIRE: 1,
            MandatoryGuideline.TYPE_ELECTRIC: 2,
        }
        active_guidelines.sort(key=lambda item: type_order.get(item.guideline_type, 99))
        pending = 0
        for guideline in active_guidelines:
            receipt, _ = MandatoryGuidelineReceipt.objects.get_or_create(guideline=guideline, user=user)
            if not receipt.is_acknowledged:
                if not state['next_mandatory_guideline_type']:
                    state['next_mandatory_guideline_type'] = guideline.guideline_type
                pending += 1
        state['pending_mandatory_guidelines_count'] = pending
        if pending:
            state['mandatory_guideline_locked'] = True
            state['next_guideline_url_name'] = 'mandatory-guidelines-inbox'
            return state

    if profile.role in {UserProfile.ROLE_WORKER, UserProfile.ROLE_SECTION_ADMIN}:
        from companies.models import ProfessionGuidelineReceipt, SectionMembership
        memberships = (
            SectionMembership.objects.filter(user=user, profession__isnull=False, profession__nizom_file__isnull=False)
            .exclude(profession__nizom_file='')
            .select_related('profession', 'section')
        )
        membership = None
        if profile.section_id:
            membership = memberships.filter(section_id=profile.section_id).order_by('-assigned_at', '-pk').first()
        if not membership:
            membership = memberships.order_by('-assigned_at', '-pk').first()
        if membership and membership.profession.nizom_file:
            state['has_profession_guideline'] = True
            receipt, _ = ProfessionGuidelineReceipt.objects.get_or_create(
                membership=membership,
                defaults={'profession': membership.profession},
            )
            if receipt.profession_id != membership.profession_id:
                receipt.profession = membership.profession
                receipt.is_acknowledged = False
                receipt.acknowledged_at = None
                receipt.save(update_fields=['profession', 'is_acknowledged', 'acknowledged_at'])
            if not receipt.is_acknowledged:
                if membership.profession.is_currently_active:
                    state['pending_profession_guidelines_count'] = 1
                    state['profession_guideline_locked'] = True
                    state['next_guideline_url_name'] = 'profession-guideline-inbox'
    return state


def get_worker_entry_guideline_context(user, is_entry_guideline_user):
    if not is_entry_guideline_user:
        return get_guideline_gate_state(user) | {'worker_entry_guideline_locked': False}
    state = get_guideline_gate_state(user)
    state['worker_entry_guideline_locked'] = bool(
        state['pending_entry_guidelines_count']
        or state['pending_mandatory_guidelines_count']
        or state['pending_profession_guidelines_count']
    )
    return state
