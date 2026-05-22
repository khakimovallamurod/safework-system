from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from core.models import StoredMediaFile


@login_required
def serve_stored_media(request, file_path):
    record = get_object_or_404(StoredMediaFile, path=file_path)
    if not record.data:
        raise Http404('Fayl bo‘sh')

    response = HttpResponse(bytes(record.data), content_type=record.content_type)
    response['Content-Length'] = record.size
    response['Content-Disposition'] = f'inline; filename="{record.filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
