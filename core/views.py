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
