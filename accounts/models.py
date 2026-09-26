from django.contrib.auth import get_user_model
from django.db import models

from industries.models import Industry

User = get_user_model()


class Region(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Viloyat nomi")

    class Meta:
        ordering = ['name']
        db_table = 'viloyat'
        verbose_name_plural = 'Regions'

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    ROLE_SUPER_ADMIN = 'super_admin'
    ROLE_ORG_LEADER = 'organization_leader'
    ROLE_DEPARTMENT_ADMIN = 'department_admin'
    ROLE_SECTION_ADMIN = 'section_admin'
    ROLE_WORKER = 'worker'
    ROLE_INSPECTION = 'inspection'

    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, 'Super admin'),
        (ROLE_ORG_LEADER, 'Tashkilot rahbari'),
        (ROLE_DEPARTMENT_ADMIN, 'Boshqarma admini'),
        (ROLE_SECTION_ADMIN, 'Bo‘lim admini'),
        (ROLE_WORKER, 'Xodim'),
        (ROLE_INSPECTION, 'Mehnat inspeksiyasi'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    full_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    phone_number = models.CharField(max_length=32, unique=True, null=True, blank=True)
    telegram_chat_id = models.CharField(max_length=64, null=True, blank=True)
    telegram_token = models.CharField(max_length=64, null=True, blank=True)
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    organization = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organization_members',
        limit_choices_to={'role': ROLE_ORG_LEADER},
        verbose_name='Tashkilot',
    )
    organization_name = models.CharField(max_length=255, blank=True)
    position = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_profiles',
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_profiles',
        verbose_name='Viloyat'
    )
    inspection_detail_access = models.BooleanField(
        default=False,
        verbose_name='Inspeksiyaga xodimlar tafsilotlarini ko‘rsatish',
        help_text='O‘chiq bo‘lsa inspeksiya faqat umumiy son va foizlarni ko‘radi.',
    )
    department = models.ForeignKey(
        'companies.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_members',
    )
    section = models.ForeignKey(
        'companies.Section',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_members',
    )
    is_new_registration = models.BooleanField(default=False)
    practice_qualified_status = models.BooleanField(
        default=False,
        verbose_name="Amaliyotdan o'tgan (ishlashga yaroqli)"
    )
    practice_qualified_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Amaliyotdan o'tgan sana"
    )
    assessment_qualified_status = models.BooleanField(
        null=True, blank=True, default=None,
        verbose_name="Bilim baholashdan o'tgan (None=sinalmagan, True=o'tdi, False=o'tmadi)"
    )
    assessment_qualified_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Bilim baholashdan o'tgan sana"
    )

    @property
    def practice_qualified(self):
        from django.utils import timezone
        if not self.practice_qualified_status:
            return False
        if not self.practice_qualified_at:
            return True
        return self.practice_qualified_at + timezone.timedelta(days=365) >= timezone.now()
        
    @practice_qualified.setter
    def practice_qualified(self, value):
        from django.utils import timezone
        self.practice_qualified_status = value
        if value:
            self.practice_qualified_at = timezone.now()

    @property
    def assessment_qualified(self):
        from django.utils import timezone
        if self.assessment_qualified_status is not True:
            return self.assessment_qualified_status
        if not self.assessment_qualified_at:
            return True
        if self.assessment_qualified_at + timezone.timedelta(days=365) < timezone.now():
            return False
        return True
        
    @assessment_qualified.setter
    def assessment_qualified(self, value):
        from django.utils import timezone
        self.assessment_qualified_status = value
        if value is True:
            self.assessment_qualified_at = timezone.now()
    # One ID (id.egov.uz) identifikatorlari
    pinfl = models.CharField(max_length=14, unique=True, null=True, blank=True, verbose_name="JShShIR (PINFL)")
    passport_series = models.CharField(max_length=10, blank=True, default='', verbose_name="Pasport seriyasi")
    passport_number = models.CharField(max_length=20, blank=True, default='', verbose_name="Pasport raqami")
    one_id_user_id = models.CharField(max_length=100, blank=True, default='', verbose_name="One ID identifikatori")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Tug‘ilgan sana")

    # Xodim ish holati (Faol, O'z hisobidan ta'til, Bo'shatilgan, Bloklangan)
    STATUS_ACTIVE = 'active'
    STATUS_ON_LEAVE = 'on_leave'
    STATUS_DISMISSED = 'dismissed'
    STATUS_BLOCKED = 'blocked'

    EMPLOYMENT_STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Faol ishlamoqda'),
        (STATUS_ON_LEAVE, 'Ta‘tilda (O‘z hisobidan / Mehnat ta‘tili)'),
        (STATUS_DISMISSED, 'Ishdan bo‘shatilgan'),
        (STATUS_BLOCKED, 'Bloklangan'),
    ]

    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default=STATUS_ACTIVE,
        verbose_name="Mehnat holati"
    )
    status_reason = models.TextField(blank=True, default='', verbose_name="Holat sababi / Izoh")
    status_changed_at = models.DateTimeField(null=True, blank=True, verbose_name="Holat o‘zgargan sana")
    status_changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='status_changed_profiles', verbose_name="Holatni o‘zgartirgan rahbar"
    )

    # Zavodga yangi kelgan xodimni Boshqarma boshlig'i qabul qilishi (9-band)
    is_approved_by_dept = models.BooleanField(
        default=False,
        verbose_name="Boshqarma tomonidan qabul qilingan"
    )
    approved_by_dept_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Boshqarma qabul qilgan sana"
    )
    approved_by_dept_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_department_workers',
        verbose_name="Qabul qilgan boshqarma boshlig'i"
    )

    is_blocked_by_violations = models.BooleanField(
        default=False, 
        verbose_name="Qoidabuzarliklar sababli bloklangan"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'foydalanuvchi'

    def __str__(self):
        return f'{self.full_name} ({self.get_role_display()})'


class UserActivitySummary(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='activity_summary')
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_path = models.CharField(max_length=255, blank=True)
    total_active_seconds = models.PositiveIntegerField(default=0)
    requests_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen_at']
        db_table = 'foydalanuvchi_faollik'
        verbose_name_plural = 'User activity summaries'

    def __str__(self):
        return f'{self.user_id} activity'


class SystemNotification(models.Model):
    TYPE_CHOICES = (
        ('guideline', "Yo'riqnoma"),
        ('test', "Test va baholash"),
        ('practice', "Ish amaliyoti"),
        ('violation', "Qoidabuzarlik"),
        ('permission', "Mehnatga ruxsat"),
        ('system', "Tizim xabari"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='system_notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='system')
    url = models.CharField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'tizim_xabarnomasi'

    def __str__(self):
        return f"{self.user.username} - {self.title}"
