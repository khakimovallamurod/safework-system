from django.contrib import messages
from django.db.models import F
from django.shortcuts import redirect
from django.utils import timezone

from accounts.models import UserActivitySummary, UserProfile
from accounts.role_navigation import (
    WORKER_ENTRY_GUIDELINE_ALLOWED_URLS,
    get_pending_entry_guidelines_count,
)


class WorkerEntryGuidelineGateMiddleware:
    """Keeps workers in the entry guideline flow until pending items are accepted."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return None

        profile = getattr(user, 'profile', None)
        if not profile or profile.role not in {UserProfile.ROLE_WORKER, UserProfile.ROLE_SECTION_ADMIN}:
            return None

        resolver_match = getattr(request, 'resolver_match', None)
        url_name = resolver_match.url_name if resolver_match else ''
        if url_name in WORKER_ENTRY_GUIDELINE_ALLOWED_URLS:
            return None

        if get_pending_entry_guidelines_count(user) == 0:
            return None

        messages.warning(
            request,
            "Avval kirish yo'riqnomasini o'qib tasdiqlang. Shundan keyin qolgan menyular ochiladi.",
        )
        return redirect('worker-entry-guidelines')


class UserActivityMiddleware:
    """Tracks lightweight usage metrics for role dashboards."""

    MAX_ACTIVE_GAP_SECONDS = 15 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._track(request)
        return response

    def _track(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return

        path = (request.path or '')[:255]
        if path.startswith('/static/') or path.startswith('/uploads/'):
            return

        now = timezone.now()
        summary, created = UserActivitySummary.objects.get_or_create(
            user=user,
            defaults={
                'first_seen_at': now,
                'last_seen_at': now,
                'last_path': path,
                'requests_count': 1,
            },
        )
        if created:
            return

        active_delta = 0
        if summary.last_seen_at:
            gap = int((now - summary.last_seen_at).total_seconds())
            if gap > 0:
                active_delta = min(gap, self.MAX_ACTIVE_GAP_SECONDS)

        UserActivitySummary.objects.filter(pk=summary.pk).update(
            last_seen_at=now,
            last_path=path,
            total_active_seconds=F('total_active_seconds') + active_delta,
            requests_count=F('requests_count') + 1,
        )
