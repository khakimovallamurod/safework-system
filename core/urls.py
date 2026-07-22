from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.http import JsonResponse
from core.views import robots_txt, sitemap_xml

urlpatterns = [
    path('', include('accounts.urls')),
    path('robots.txt', robots_txt, name='robots-txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap'),
    path('roles/super-admin/', include('super_admin.urls')),
    path('roles/tashkilot-rahbari/', include('organization_leader.urls')),
    path('roles/boshqarma-rahbari/', include('department_admin.urls')),
    path('roles/bolim-boshligi/', include('section_admin.urls')),
    path('roles/ishchi/', include('worker.urls')),
    path('industries/', include('industries.urls')),
    path('companies/', include('companies.urls')),
    path('professions/', include('professions.urls')),
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: JsonResponse({})),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
