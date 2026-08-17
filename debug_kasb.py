import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserProfile
from companies.models import SectionMembership
from accounts.role_navigation import get_guideline_gate_state
import json

users = User.objects.filter(profile__role__in=[UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_DEPARTMENT_ADMIN])
for u in users:
    profile = u.profile
    memberships = SectionMembership.objects.filter(user=u)
    
    print(f"\n--- User: {u.username} | Full name: {profile.full_name} | Role: {profile.role} ---")
    
    state = get_guideline_gate_state(u)
    print(f"has_profession_guideline: {state['has_profession_guideline']}, profession_guideline_locked: {state['profession_guideline_locked']}")
    
    if not memberships.exists():
        print("  -> No SectionMembership found for this user.")
    else:
        for m in memberships:
            prof = m.profession
            if prof:
                has_pdf = bool(prof.nizom_file)
                print(f"  -> Membership (Section: {m.section}): Profession = {prof.name}, PDF = {has_pdf}")
            else:
                print(f"  -> Membership (Section: {m.section}): Profession = None")

