import mimetypes

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.utils.encoding import filepath_to_uri


@deconstructible
class DatabaseStorage(Storage):
    """Fayllarni disk o'rniga StoredMediaFile jadvalida saqlaydi."""

    def _open(self, name, mode='rb'):
        from core.models import StoredMediaFile

        record = StoredMediaFile.objects.get(path=name)
        return ContentFile(bytes(record.data), name=name)

    def _save(self, name, content):
        from core.models import StoredMediaFile

        if hasattr(content, 'chunks'):
            chunks = []
            for chunk in content.chunks():
                chunks.append(chunk)
            data = b''.join(chunks)
        else:
            content.seek(0)
            data = content.read()

        content_type = getattr(content, 'content_type', None) or mimetypes.guess_type(name)[0] or 'application/octet-stream'
        StoredMediaFile.objects.update_or_create(
            path=name,
            defaults={
                'data': data,
                'content_type': content_type,
                'size': len(data),
            },
        )
        return name

    def delete(self, name):
        if not name:
            return
        from core.models import StoredMediaFile

        StoredMediaFile.objects.filter(path=name).delete()

    def exists(self, name):
        if not name:
            return False
        from core.models import StoredMediaFile

        return StoredMediaFile.objects.filter(path=name).exists()

    def size(self, name):
        from core.models import StoredMediaFile

        return StoredMediaFile.objects.get(path=name).size

    def url(self, name):
        if not name:
            return ''
        base = settings.MEDIA_URL.rstrip('/')
        return f'{base}/{filepath_to_uri(name)}'
