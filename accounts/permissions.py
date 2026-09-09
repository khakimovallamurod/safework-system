"""Role-Based Access Control (RBAC) and permissions management.

Provides a decoupled, extensible permission architecture.
New roles can be registered with specific feature sets without modifying
core business logic throughout the application.
"""

from accounts.models import UserProfile

# ─── Permission Codes ──────────────────────────────────────────────────────────

# Yo'riqnomalar (Guidelines)
PERM_GUIDELINE_READ = 'guideline.read'                  # O'qish, ko'rish va qabul qilish
PERM_GUIDELINE_MANAGE = 'guideline.manage'              # Yaratish, tahrirlash, o'chirish, jo'natish
PERM_GUIDELINE_STOP = 'guideline.stop'                  # Muddatidan oldin to'xtatish (izoh bilan)
PERM_GUIDELINE_REPORT_VIEW = 'guideline.report.view'    # Yo'riqnoma holati va hisobotlarini ko'rish

# Bilimni baholash / Testlar (Assessments)
PERM_ASSESSMENT_TAKE = 'assessment.take'                # Test topshirish
PERM_ASSESSMENT_MANAGE = 'assessment.manage'            # Savollar bazasi, test yaratish, tahrirlash, o'chirish
PERM_ASSESSMENT_STOP = 'assessment.stop'                # Testni oldindan to'xtatish (izoh bilan)
PERM_ASSESSMENT_REPORT_VIEW = 'assessment.report.view'  # Natijalar va hisobotlarni ko'rish

# Bo'limlar va Xodimlar (Sections & Workers)
PERM_SECTIONS_VIEW = 'sections.view'                    # Bo'limlarni ko'rish
PERM_SECTIONS_MANAGE = 'sections.manage'                # Bo'limlarni yaratish/tahrirlash/o'chirish
PERM_WORKERS_VIEW = 'workers.view'                      # Xodimlarni ko'rish
PERM_WORKERS_MANAGE = 'workers.manage'                  # Xodimlarni biriktirish, tahrirlash
PERM_MEDICAL_RECORDS_VIEW = 'medical.view'              # Tibbiy ma'lumotlarni ko'rish
PERM_MEDICAL_RECORDS_MANAGE = 'medical.manage'          # Tibbiy ma'lumotlarni kiritish/tahrirlash

# Mehnat muhofazasi va Xavfsizlik (Safety, PPE, Violations)
PERM_PPE_VIEW = 'ppe.view'
PERM_PPE_MANAGE = 'ppe.manage'
PERM_VIOLATIONS_VIEW = 'violations.view'
PERM_VIOLATIONS_MANAGE = 'violations.manage'
PERM_CERTIFICATES_VIEW = 'certificates.view'
PERM_CERTIFICATES_MANAGE = 'certificates.manage'
PERM_PROFESSIONS_VIEW = 'professions.view'
PERM_PROFESSIONS_MANAGE = 'professions.manage'

# Tashkilot va Tizim boshqaruvi (Org & System)
PERM_ORG_MANAGE = 'org.manage'
PERM_SYSTEM_SETTINGS = 'system.settings'


# ─── Role Permissions Matrix ──────────────────────────────────────────────────
# Kelajakda yangi rol qo'shilsa yoki biror rolga yangi imkoniyat berilsa,
# faqat ushbu lug'atga mos ruxsatlar kiritiladi.

ROLE_PERMISSIONS = {
    # 1. Xodim (Worker): faqat o'qish, test topshirish, o'z sertifikat/tibbiy ma'lumotlarini ko'rish
    UserProfile.ROLE_WORKER: {
        PERM_GUIDELINE_READ,
        PERM_ASSESSMENT_TAKE,
        PERM_PPE_VIEW,
        PERM_VIOLATIONS_VIEW,
        PERM_CERTIFICATES_VIEW,
        PERM_MEDICAL_RECORDS_VIEW,
    },

    # 2. Bo'lim nazoratchisi (Section Admin):
    UserProfile.ROLE_SECTION_ADMIN: {
        PERM_GUIDELINE_READ,
        PERM_GUIDELINE_MANAGE,        # Ichki yo'riqnomalarni boshqarish
        PERM_GUIDELINE_STOP,
        PERM_GUIDELINE_REPORT_VIEW,
        PERM_ASSESSMENT_TAKE,
        PERM_WORKERS_VIEW,
        PERM_WORKERS_MANAGE,          # Bo'lim xodimlarini boshqarish
        PERM_PPE_VIEW,
        PERM_PPE_MANAGE,
        PERM_VIOLATIONS_VIEW,
        PERM_VIOLATIONS_MANAGE,
        PERM_CERTIFICATES_VIEW,
        PERM_CERTIFICATES_MANAGE,
        PERM_MEDICAL_RECORDS_VIEW,
    },

    # 3. Boshqarma nazoratchisi (Department Admin):
    # O'z boshqarmasi miqyosida barcha boshqaruv, to'xtatish va monitoring
    UserProfile.ROLE_DEPARTMENT_ADMIN: {
        PERM_GUIDELINE_READ,
        PERM_GUIDELINE_MANAGE,
        PERM_GUIDELINE_STOP,
        PERM_GUIDELINE_REPORT_VIEW,
        PERM_ASSESSMENT_MANAGE,
        PERM_ASSESSMENT_STOP,
        PERM_ASSESSMENT_REPORT_VIEW,
        PERM_SECTIONS_VIEW,
        PERM_SECTIONS_MANAGE,
        PERM_WORKERS_VIEW,
        PERM_WORKERS_MANAGE,
        PERM_MEDICAL_RECORDS_VIEW,
        PERM_MEDICAL_RECORDS_MANAGE,
        PERM_PPE_VIEW,
        PERM_PPE_MANAGE,
        PERM_VIOLATIONS_VIEW,
        PERM_VIOLATIONS_MANAGE,
        PERM_CERTIFICATES_VIEW,
        PERM_CERTIFICATES_MANAGE,
        PERM_PROFESSIONS_VIEW,
        PERM_PROFESSIONS_MANAGE,
    },

    # 4. Tashkilot rahbari (Organization Leader):
    UserProfile.ROLE_ORG_LEADER: {
        PERM_GUIDELINE_READ,
        PERM_GUIDELINE_MANAGE,
        PERM_GUIDELINE_STOP,
        PERM_GUIDELINE_REPORT_VIEW,
        PERM_ASSESSMENT_MANAGE,
        PERM_ASSESSMENT_STOP,
        PERM_ASSESSMENT_REPORT_VIEW,
        PERM_SECTIONS_VIEW,
        PERM_SECTIONS_MANAGE,
        PERM_WORKERS_VIEW,
        PERM_WORKERS_MANAGE,
        PERM_MEDICAL_RECORDS_VIEW,
        PERM_MEDICAL_RECORDS_MANAGE,
        PERM_PPE_VIEW,
        PERM_PPE_MANAGE,
        PERM_VIOLATIONS_VIEW,
        PERM_VIOLATIONS_MANAGE,
        PERM_CERTIFICATES_VIEW,
        PERM_CERTIFICATES_MANAGE,
        PERM_PROFESSIONS_VIEW,
        PERM_PROFESSIONS_MANAGE,
        PERM_ORG_MANAGE,
    },

    # 5. Super Admin:
    UserProfile.ROLE_SUPER_ADMIN: {
        PERM_GUIDELINE_READ,
        PERM_GUIDELINE_MANAGE,
        PERM_GUIDELINE_STOP,
        PERM_GUIDELINE_REPORT_VIEW,
        PERM_ASSESSMENT_MANAGE,
        PERM_ASSESSMENT_STOP,
        PERM_ASSESSMENT_REPORT_VIEW,
        PERM_SECTIONS_VIEW,
        PERM_SECTIONS_MANAGE,
        PERM_WORKERS_VIEW,
        PERM_WORKERS_MANAGE,
        PERM_MEDICAL_RECORDS_VIEW,
        PERM_MEDICAL_RECORDS_MANAGE,
        PERM_PPE_VIEW,
        PERM_PPE_MANAGE,
        PERM_VIOLATIONS_VIEW,
        PERM_VIOLATIONS_MANAGE,
        PERM_CERTIFICATES_VIEW,
        PERM_CERTIFICATES_MANAGE,
        PERM_PROFESSIONS_VIEW,
        PERM_PROFESSIONS_MANAGE,
        PERM_ORG_MANAGE,
        PERM_SYSTEM_SETTINGS,
    },
}


# ─── Helper Functions ─────────────────────────────────────────────────────────

def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return UserProfile.ROLE_SUPER_ADMIN
    profile = getattr(user, 'profile', None)
    return profile.role if profile else None


def get_user_permissions(user):
    """Foydalanuvchining barcha ruxsat kodlari to'plamini qaytaradi."""
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        all_perms = set()
        for perms in ROLE_PERMISSIONS.values():
            all_perms |= perms
        return all_perms

    role = get_user_role(user)
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(user, perm_code):
    """Berilgan foydalanuvchida ko'rsatilgan ruxsat kodi mavjudligini tekshiradi."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return perm_code in get_user_permissions(user)


def has_any_permission(user, *perm_codes):
    """Ko'rsatilgan ruxsat kodlaridan kamida bittasi mavjudligini tekshiradi."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    user_perms = get_user_permissions(user)
    return any(p in user_perms for p in perm_codes)
