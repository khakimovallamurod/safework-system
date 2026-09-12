from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone


def robots_txt(request):
    base_url = f"{request.scheme}://{request.get_host()}"
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {base_url}{reverse('sitemap')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    base_url = f"{request.scheme}://{request.get_host()}"
    today = timezone.localdate().isoformat()
    urls = [
        {
            "loc": f"{base_url}{reverse('home')}",
            "changefreq": "weekly",
            "priority": "1.0",
        },
        {
            "loc": f"{base_url}{reverse('login')}",
            "changefreq": "monthly",
            "priority": "0.4",
        },
        {
            "loc": f"{base_url}{reverse('register-choice')}",
            "changefreq": "monthly",
            "priority": "0.5",
        },
    ]
    items = "\n".join(
        (
            "  <url>"
            f"<loc>{url['loc']}</loc>"
            f"<lastmod>{today}</lastmod>"
            f"<changefreq>{url['changefreq']}</changefreq>"
            f"<priority>{url['priority']}</priority>"
            "</url>"
        )
        for url in urls
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n'
    return HttpResponse(xml, content_type="application/xml")


import base64
from urllib.parse import urlparse, parse_qs
from django.urls import resolve
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

@login_required
@csrf_protect
def secure_spa_gateway(request):
    """
    Xavfsiz SPA Shlyuzi (Network Obfuscation & Security Gate):
    Brauzerning DevTools Network panelida ichki yo'nalishlar (endpointlar) va
    parametrlarni oshkor qilmaslik uchun so'rovlarni shifrlangan token orqali qabul qiladi.
    """
    if request.method != 'POST':
        return HttpResponseForbidden("Faqat xavfsiz POST so‘rovlar qabul qilinadi.")

    token = request.POST.get('token') or request.headers.get('X-Sopline-Token')
    if not token:
        return HttpResponseForbidden("Xavfsizlik belgisi yetishmaydi.")

    try:
        raw_target = base64.b64decode(token.encode('utf-8')).decode('utf-8')
        if not raw_target.startswith('/'):
            return HttpResponseForbidden("Noto‘g‘ri yo‘nalish.")

        parsed = urlparse(raw_target)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Xavfsiz simulyatsiya: view uchun ichki GET so'rovini sozlash
        request.path_info = path
        request.path = path
        request.method = 'GET'
        request.GET = request.GET.copy()
        for k, v in query.items():
            request.GET.setlist(k, v)

        match = resolve(path)
        response = match.func(request, *match.args, **match.kwargs)
        # Keshlanishni va tarmoq orqali sizib chiqishni oldini olish
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        response['X-Sopline-Protected'] = '1'
        return response
    except Exception:
        return HttpResponseForbidden("Ruxsatsiz yo‘nalish.")
