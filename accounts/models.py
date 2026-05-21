from django.contrib.auth import get_user_model
from django.db import models

from industries.models import Industry

User = get_user_model()


class UserProfile(models.Model):
    ROLE_ORG_LEADER = 'organization_leader'
    ROLE_DEPARTMENT_ADMIN = 'department_admin'
    ROLE_SECTION_ADMIN = 'section_admin'
    ROLE_WORKER = 'worker'

    ROLE_CHOICES = [
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} ({self.get_role_display()})'
