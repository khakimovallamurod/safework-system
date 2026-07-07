from django.contrib.auth import get_user_model
from django.db import models

from industries.models import Industry

User = get_user_model()


class UserProfile(models.Model):
    ROLE_SUPER_ADMIN = 'super_admin'
    ROLE_ORG_LEADER = 'organization_leader'
    ROLE_DEPARTMENT_ADMIN = 'department_admin'
    ROLE_SECTION_ADMIN = 'section_admin'
    ROLE_WORKER = 'worker'

    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, 'Super admin'),
        (ROLE_ORG_LEADER, 'Tashkilot rahbari'),
        (ROLE_DEPARTMENT_ADMIN, 'Boshqarma admini'),
        (ROLE_SECTION_ADMIN, 'Bo‘lim admini'),
        (ROLE_WORKER, 'Xodim'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    full_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    phone_number = models.CharField(max_length=32, unique=True, null=True, blank=True)
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
    practice_qualified = models.BooleanField(
        default=False,
        verbose_name="Amaliyotdan o'tgan (ishlashga yaroqli)"
    )
    assessment_qualified = models.BooleanField(
        null=True, blank=True, default=None,
        verbose_name="Bilim baholashdan o'tgan (None=sinalmagan, True=o'tdi, False=o'tmadi)"
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
