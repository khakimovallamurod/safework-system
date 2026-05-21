from django.urls import include, path

from core.views import serve_stored_media

urlpatterns = [
    path('', include('accounts.urls')),
    path('industries/', include('industries.urls')),
    path('companies/', include('companies.urls')),
    path('professions/', include('professions.urls')),
    path('media/<path:file_path>', serve_stored_media, name='serve-stored-media'),
]
