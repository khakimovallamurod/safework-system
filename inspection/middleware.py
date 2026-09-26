import base64
from urllib.parse import urlparse

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from accounts.models import UserProfile


# Inspeksiya modulidan tashqarida inspektorga ochiq bo'lgan sahifalar (o'z akkaunti bilan bog'liq).
INSPECTOR_ALLOWED_URL_NAMES = {
    'logout',
    'dashboard',  # inspection:dashboard ga yo'naltiradi
    'profile',
    'profile-update',
    'notifications',
    'notification-mark-read',
    'telegram-connect',
    'telegram-check',
    'serve-stored-media',
}

# O'z akkaunti uchun yozishga ruxsat etilgan yagona amallar.
INSPECTOR_WRITE_URL_NAMES = {
    'logout',
    'profile-update',
    'notification-mark-read',
    'telegram-connect',
    'telegram-check',
}

SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


def _is_allowed_view(match):
    if match.namespace == 'inspection':
        return match.url_name not in {'admin-manage', 'toggle-status'}
    return not match.namespace and match.url_name in INSPECTOR_ALLOWED_URL_NAMES


def _spa_target_match(request):
    token = request.POST.get('token') or request.headers.get('X-Sopline-Token')
    if not token:
        return None
    try:
        path = urlparse(base64.b64decode(token.encode('utf-8')).decode('utf-8')).path
        return resolve(path)
    except (ValueError, UnicodeDecodeError, Resolver404):
        return None


class InspectionReadOnlyMiddleware:
    """Mehnat inspeksiyasi roli uchun qat'iy READ-ONLY rejim.

    Inspektor faqat inspeksiya modulidagi sahifalarni ko'radi; ma'lumotni o'zgartiruvchi
    har qanday so'rov (POST/PUT/PATCH/DELETE) o'z akkaunti bilan bog'liq amallardan tashqari rad etiladi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return None
        profile = getattr(user, 'profile', None)
        if not profile or profile.role != UserProfile.ROLE_INSPECTION:
            return None

        path = request.path or ''
        if path.startswith('/static/') or path.startswith('/uploads/'):
            return None

        match = request.resolver_match
        if match is None:
            return None

        # SPA shlyuzi ichki GET so'rovini boshqa view'ga uzatadi — nishon sahifani tekshiramiz.
        if match.url_name == 'secure-spa-gateway':
            target = _spa_target_match(request)
            if target is None or not _is_allowed_view(target):
                return HttpResponseForbidden('Mehnat inspeksiyasi faqat kuzatish rejimida ishlaydi.')
            return None

        if request.method not in SAFE_METHODS:
            if not match.namespace and match.url_name in INSPECTOR_WRITE_URL_NAMES:
                return None
            return HttpResponseForbidden('Mehnat inspeksiyasi faqat kuzatish (read-only) rejimida ishlaydi.')

        if not _is_allowed_view(match):
            messages.info(request, 'Mehnat inspeksiyasi faqat kuzatish rejimida ishlaydi.')
            return redirect('inspection:dashboard')
        return None
