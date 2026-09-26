from django.db import models
from django.contrib.auth.models import User
from accounts.models import UserProfile, Region


class InspectionNote(models.Model):
    """Inspektorning korxona bo'yicha kiritgan nazorat qaydlari / xulosalari"""
    inspector = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='inspection_notes',
        verbose_name="Inspektor"
    )
    organization = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='inspection_notes',
        verbose_name="Tashkilot rahbari / Korxona"
    )
    title = models.CharField(max_length=255, verbose_name="Mavzu / Tekshiruv predmeti")
    notes = models.TextField(verbose_name="Ko'rsatma / Qayd / Kamchiliklar")
    is_resolved = models.BooleanField(default=False, verbose_name="Bartaraf etilgan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inspeksiya qaydi'
        verbose_name_plural = 'Inspeksiya qaydlari'

    def __str__(self):
        return f"{self.title} - {self.organization.organization_name}"
