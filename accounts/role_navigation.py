from companies.guidelines import (
    current_entry_receipt,
    current_mandatory_guidelines,
    current_profession_membership,
    profession_guideline_receipt,
)


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
        
    # Faqat joriy (eng so'nggi, to'xtatilmagan) kirish yo'riqnomasi hisobga olinadi
    receipt = current_entry_receipt(user, create=True)
    if not receipt:
        return 0
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
    if not profile or profile.role not in {UserProfile.ROLE_WORKER, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_DEPARTMENT_ADMIN}:
        return state

    entry_pending = get_pending_entry_guidelines_count(user)
    state['pending_entry_guidelines_count'] = entry_pending
    if entry_pending:
        state['worker_entry_guideline_locked'] = True
        state['next_guideline_url_name'] = 'worker-entry-guidelines'

    # 9-band: Ishchi faqat uchastkaga biriktirilgandan keyin qolgan majburiy va kasbiy yo'riqnomalar ochiladi
    can_access_advanced_guidelines = (profile.role != UserProfile.ROLE_WORKER) or bool(profile.section_id)

    if profile.department_id and can_access_advanced_guidelines:
        from companies.models import MandatoryGuidelineReceipt
        # Har bir tur bo'yicha faqat bitta — eng so'nggi faol (to'xtatilmagan) yo'riqnoma
        active_guidelines = current_mandatory_guidelines(profile.department_id)
        acknowledged_ids = set(
            MandatoryGuidelineReceipt.objects.filter(
                user=user,
                guideline__in=active_guidelines,
                is_acknowledged=True,
            ).values_list('guideline_id', flat=True)
        )
        pending = 0
        for guideline in active_guidelines:
            if guideline.pk not in acknowledged_ids:
                if not state['next_mandatory_guideline_type']:
                    state['next_mandatory_guideline_type'] = guideline.guideline_type
                pending += 1
        state['pending_mandatory_guidelines_count'] = pending
        if pending:
            state['mandatory_guideline_locked'] = True
            if not state['next_guideline_url_name']:
                state['next_guideline_url_name'] = 'mandatory-guidelines-inbox'

    if can_access_advanced_guidelines and profile.role in {UserProfile.ROLE_WORKER, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_DEPARTMENT_ADMIN}:
        # Gate, inbox, PDF va qabul bir xil a'zolikni tanlashi uchun umumiy helper
        membership = current_profession_membership(user)
        if membership and membership.profession.nizom_file:
            state['has_profession_guideline'] = True
            receipt = profession_guideline_receipt(membership)
            if not receipt.is_acknowledged:
                if membership.profession.is_currently_active:
                    state['pending_profession_guidelines_count'] = 1
                    state['profession_guideline_locked'] = True
                    if not state['next_guideline_url_name']:
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
