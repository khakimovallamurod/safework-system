from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from industries.models import Industry


def validate_file_size_1mb(value):
    max_bytes = 1024 * 1024
    if value.size > max_bytes:
        raise ValidationError("Nizom fayli 1MB dan oshmasligi kerak.")


class Profession(models.Model):
    name = models.CharField(max_length=255)
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, related_name='professions')
    nizom_file = models.FileField(
        upload_to='nizom_files/',
        validators=[FileExtensionValidator(['pdf']), validate_file_size_1mb],
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('name', 'industry')

    def __str__(self):
        return f"{self.name} ({self.industry.name})"
