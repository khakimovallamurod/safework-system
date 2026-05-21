from django.db import models


class StoredMediaFile(models.Model):
    """Barcha yuklangan rasmlar va PDF lar bazada saqlanadi."""

    path = models.CharField(max_length=255, unique=True, db_index=True)
    data = models.BinaryField()
    content_type = models.CharField(max_length=128, default='application/octet-stream')
    size = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Saqlangan fayl'
        verbose_name_plural = 'Saqlangan fayllar'

    def __str__(self):
        return self.path

    @property
    def filename(self):
        return self.path.rsplit('/', 1)[-1] if self.path else 'file'
