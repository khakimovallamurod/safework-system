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
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, related_name='professions')
    nizom_file = models.FileField(
        upload_to='nizom_files/',
        validators=[FileExtensionValidator(['pdf', 'docx']), validate_file_size_20mb],
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('name', 'industry')

    def __str__(self):
        return f"{self.name} ({self.industry.name})"
