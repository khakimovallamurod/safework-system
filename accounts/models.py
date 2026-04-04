from django.contrib.auth import get_user_model
from django.db import models

from industries.models import Industry

User = get_user_model()


class UserProfile(models.Model):
    ROLE_ORG_LEADER = 'organization_leader'
    ROLE_WORKER = 'worker'

    ROLE_CHOICES = [
        (ROLE_ORG_LEADER, 'Tashkilot rahbari'),
        (ROLE_WORKER, 'Ishchi'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    full_name = models.CharField(max_length=255)
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
    is_new_registration = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} ({self.get_role_display()})'
