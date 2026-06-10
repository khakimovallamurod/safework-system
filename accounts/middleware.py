from django.contrib import messages
from django.shortcuts import redirect

from accounts.models import UserProfile
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
