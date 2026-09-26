from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from industries.models import Industry


def validate_file_size_20mb(value):
    max_bytes = 20 * 1024 * 1024
    if value.size > max_bytes:
        raise ValidationError("Nizom fayli 20MB dan oshmasligi kerak.")


class Profession(models.Model):
    name = models.CharField(max_length=255)
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, related_name='professions', null=True, blank=True)
    organization = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='org_professions',
        limit_choices_to={'role': 'organization_leader'}
    )
    department = models.ForeignKey(
        'companies.Department',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dept_professions'
    )
    nizom_file = models.FileField(
        upload_to='nizom_files/',
        validators=[FileExtensionValidator(['pdf', 'docx']), validate_file_size_20mb],
        blank=True,
        null=True,
    )
    start_time = models.DateTimeField(null=True, blank=True)
    active_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_currently_active(self):
        if not self.start_time or not self.active_until:
            return True
        from companies.guidelines import is_within_window
        return is_within_window(self.start_time, self.active_until)

    @property
    def has_started(self):
        from companies.guidelines import has_started
        return has_started(self.start_time)

    @property
    def is_expired(self):
        from companies.guidelines import is_expired
        return is_expired(self.active_until)

    @property
    def days_left(self):
        from companies.guidelines import days_left
        return days_left(self.active_until)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        industry_name = self.industry.name if self.industry else "Soha belgilanmagan"
        return f"{self.name} ({industry_name})"
