from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path('', include('accounts.urls')),
    path('roles/super-admin/', include('super_admin.urls')),
    path('roles/tashkilot-rahbari/', include('organization_leader.urls')),
    path('roles/boshqarma-rahbari/', include('department_admin.urls')),
    path('roles/bolim-boshligi/', include('section_admin.urls')),
    path('roles/ishchi/', include('worker.urls')),
    path('industries/', include('industries.urls')),
    path('companies/', include('companies.urls')),
    path('professions/', include('professions.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

